"""Trend analysis module for analyzing HDC trends over time."""
import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import sqlite3

from agents import Agent, Runner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


@dataclass
class TrendTopic:
    """Represents a trend topic with its metadata."""
    name: str
    start_date: str  # YYYY-MM-DD
    end_date: Optional[str]  # YYYY-MM-DD or None if still active
    total_mentions: int
    peak_week: str  # YYYY-MM-DD of week with most mentions
    peak_count: int


@dataclass
class TrendDataPoint:
    """A single data point in a trend time series."""
    period: str  # Week identifier (YYYY-WW or YYYY-MM)
    date: str  # YYYY-MM-DD
    count: int


@dataclass
class TrendAnalysis:
    """Complete trend analysis result."""
    analysis_date: str  # YYYY-MM-DD
    top_topics: List[TrendTopic]
    time_series: Dict[str, List[TrendDataPoint]]  # topic_name -> list of data points
    period_type: str  # "week", "month", or "year"


DB_PATH = Path("hdc_digest.db")
SYSTEM_PROMPT = """
You are an expert at analyzing research trends in Hyperdimensional Computing (HDC).

Extract key topics, themes, and research directions from the provided content.
Focus on:
- Technical concepts (binding, bundling, permutation, HRR, SPA, MAP, etc.)
- Application domains (neuromorphic computing, hardware, machine learning, etc.)
- Research directions (efficiency, scalability, new architectures, etc.)

Return ONLY a JSON array of topic strings, each 2-5 words.
Example: ["binding operations", "neuromorphic hardware", "vector symbolic architectures"]
"""


def _get_db_connection() -> sqlite3.Connection:
    """Get a database connection with proper configuration."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _extract_topics_from_items(items: List[Dict[str, Any]], agent: Agent) -> List[str]:
    """Extract topics from a list of items using an agent."""
    if not items:
        return []
    
    # Combine titles and summaries for analysis
    content = []
    for item in items[:50]:  # Limit to avoid token limits
        content.append({
            "title": item.get("title", ""),
            "summary": item.get("summary", ""),
        })
    
    prompt = f"""
Analyze the following HDC research items and extract the main topics/themes.

Items:
{json.dumps(content, indent=2)}

Return ONLY a JSON array of topic strings (2-5 words each).
Focus on recurring themes and important research directions.
Return 10-20 topics.
"""
    
    try:
        result = Runner.run_sync(agent, prompt)
        # Extract JSON from response
        text = result.final_output.strip()
        # Try to extract JSON array
        json_match = re.search(r'\[.*?\]', text, re.DOTALL)
        if json_match:
            topics = json.loads(json_match.group(0))
            return [str(t).strip() for t in topics if t]
        # Fallback: try parsing the whole response
        topics = json.loads(text)
        return [str(t).strip() for t in topics if isinstance(topics, list) and t]
    except Exception as e:
        logger.warning(f"Failed to extract topics via agent: {e}")
        # Fallback to keyword-based extraction
        return _extract_topics_keywords(items)


def _extract_topics_keywords(items: List[Dict[str, Any]]) -> List[str]:
    """Fallback keyword-based topic extraction."""
    # Common HDC topics/keywords
    keywords = {
        "binding operations": ["binding", "bundling"],
        "vector symbolic architectures": ["VSA", "vector symbolic"],
        "neuromorphic computing": ["neuromorphic", "brain-inspired"],
        "hardware acceleration": ["hardware", "FPGA", "ASIC"],
        "machine learning": ["learning", "classification", "neural"],
        "permutation operations": ["permutation", "shift"],
        "hypervector encoding": ["encoding", "hypervector"],
        "similarity search": ["similarity", "search", "retrieval"],
        "energy efficiency": ["energy", "efficient", "power"],
        "scalability": ["scalable", "scale", "large-scale"],
    }
    
    topic_counts = defaultdict(int)
    all_text = " ".join([
        item.get("title", "") + " " + item.get("summary", "")
        for item in items
    ]).lower()
    
    for topic, keys in keywords.items():
        for key in keys:
            if key.lower() in all_text:
                topic_counts[topic] += all_text.count(key.lower())
                break
    
    # Return top topics
    sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
    return [topic for topic, count in sorted_topics[:15] if count > 0]


def _get_items_by_time_period(
    start_date: str,
    end_date: str,
    period_type: str = "week"
) -> Dict[str, List[Dict[str, Any]]]:
    """Get items grouped by time period."""
    conn = _get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT * FROM items
            WHERE first_seen_date >= ? AND first_seen_date <= ?
            ORDER BY first_seen_date ASC
        """, (start_date, end_date))
        
        items = [dict(row) for row in cursor.fetchall()]
        
        # Group by time period
        period_items: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        for item in items:
            date_str = item.get("first_seen_date", "")
            if not date_str:
                continue
            
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d").date()
                
                if period_type == "week":
                    # Use ISO week format: YYYY-WW
                    year, week, _ = date.isocalendar()
                    period = f"{year}-W{week:02d}"
                elif period_type == "month":
                    period = date.strftime("%Y-%m")
                elif period_type == "year":
                    period = date.strftime("%Y")
                else:
                    period = date_str
                
                period_items[period].append(item)
            except ValueError:
                logger.warning(f"Invalid date format: {date_str}")
                continue
        
        return dict(period_items)
    finally:
        conn.close()


def _calculate_topic_mentions(
    items: List[Dict[str, Any]],
    topic: str
) -> int:
    """Count how many items mention a topic."""
    topic_lower = topic.lower()
    count = 0
    for item in items:
        title = item.get("title", "").lower()
        summary = item.get("summary", "").lower()
        combined = title + " " + summary
        if topic_lower in combined:
            count += 1
    return count


def _build_time_series(
    period_items: Dict[str, List[Dict[str, Any]]],
    topics: List[str],
    period_type: str
) -> Dict[str, List[TrendDataPoint]]:
    """Build time series data for each topic."""
    time_series: Dict[str, List[TrendDataPoint]] = {topic: [] for topic in topics}
    
    # Sort periods chronologically
    sorted_periods = sorted(period_items.keys())
    
    for period in sorted_periods:
        items = period_items[period]
        # Get the date for this period (use first item's date or period start)
        if items:
            date_str = items[0].get("first_seen_date", "")
        else:
            # Parse period to get a representative date
            if period_type == "week":
                year, week = map(int, period.split("-W"))
                # Approximate: first day of week
                date_str = datetime.strptime(f"{year}-W{week:02d}-1", "%Y-W%W-%w").date().isoformat()
            elif period_type == "month":
                date_str = f"{period}-01"
            else:
                date_str = f"{period}-01-01"
        
        for topic in topics:
            count = _calculate_topic_mentions(items, topic)
            time_series[topic].append(TrendDataPoint(
                period=period,
                date=date_str,
                count=count
            ))
    
    return time_series


def _identify_active_topics(
    time_series: Dict[str, List[TrendDataPoint]],
    min_gap_weeks: int = 4
) -> Dict[str, Tuple[str, Optional[str]]]:
    """Identify when topics start and stop being active.
    
    A topic stops if it has no mentions for more than min_gap_weeks.
    """
    topic_periods: Dict[str, Tuple[str, Optional[str]]] = {}
    
    for topic, points in time_series.items():
        if not points:
            continue
        
        # Find first and last non-zero mentions
        non_zero_points = [p for p in points if p.count > 0]
        if not non_zero_points:
            continue
        
        start_date = non_zero_points[0].date
        last_active_date = non_zero_points[-1].date
        
        # Check if topic has been inactive for too long
        # Find the last data point
        last_point = points[-1]
        last_point_date = datetime.strptime(last_point.date, "%Y-%m-%d").date()
        last_active_date_obj = datetime.strptime(last_active_date, "%Y-%m-%d").date()
        
        gap_weeks = (last_point_date - last_active_date_obj).days / 7
        
        end_date = None
        if gap_weeks > min_gap_weeks:
            # Topic has stopped
            end_date = last_active_date
        
        topic_periods[topic] = (start_date, end_date)
    
    return topic_periods


def analyze_trends(
    weeks_back: int = 52,
    top_n: int = 15,
    period_type: str = "week",
    use_agent: bool = True
) -> TrendAnalysis:
    """Analyze trends in the database.
    
    Args:
        weeks_back: Number of weeks to analyze
        top_n: Number of top topics to return
        period_type: "week", "month", or "year"
        use_agent: Whether to use agent for topic extraction (fallback to keywords if False)
    
    Returns:
        TrendAnalysis with top topics and time series data
    """
    logger.info(f"Starting trend analysis (weeks_back={weeks_back}, period_type={period_type})")
    
    # Ensure database and items table exist (idempotent)
    from .store import _init_db
    _init_db()

    # Calculate date range
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(weeks=weeks_back)
    
    # Get all items in the date range
    logger.info(f"Fetching items from {start_date} to {end_date}")
    period_items = _get_items_by_time_period(
        start_date.isoformat(),
        end_date.isoformat(),
        period_type
    )
    
    # Flatten all items for topic extraction
    all_items = []
    for items in period_items.values():
        all_items.extend(items)
    
    logger.info(f"Found {len(all_items)} items across {len(period_items)} periods")
    
    # Extract topics
    if use_agent:
        logger.info("Extracting topics using agent...")
        from .digest import build_agent
        agent = build_agent()
        agent.instructions = SYSTEM_PROMPT
        topics = _extract_topics_from_items(all_items, agent)
    else:
        logger.info("Extracting topics using keywords...")
        topics = _extract_topics_keywords(all_items)
    
    logger.info(f"Extracted {len(topics)} topics")
    
    # Build time series for all topics
    logger.info("Building time series...")
    time_series = _build_time_series(period_items, topics, period_type)
    
    # Calculate total mentions and peak periods for each topic
    topic_stats: List[Tuple[str, int, str, int]] = []
    for topic, points in time_series.items():
        total = sum(p.count for p in points)
        if total == 0:
            continue
        
        # Find peak period
        peak_point = max(points, key=lambda p: p.count)
        topic_stats.append((topic, total, peak_point.period, peak_point.count))
    
    # Sort by total mentions and take top N
    topic_stats.sort(key=lambda x: x[1], reverse=True)
    top_topics_data = topic_stats[:top_n]
    
    # Identify active periods for topics
    topic_periods = _identify_active_topics(time_series)
    
    # Build TrendTopic objects
    top_topics = []
    for topic, total, peak_period, peak_count in top_topics_data:
        start_date_str, end_date_str = topic_periods.get(topic, (None, None))
        if start_date_str is None:
            # Find first non-zero point
            points = time_series[topic]
            first_active = next((p for p in points if p.count > 0), None)
            start_date_str = first_active.date if first_active else ""
        
        # Find peak week date
        peak_point = max(time_series[topic], key=lambda p: p.count)
        peak_week = peak_point.date
        
        top_topics.append(TrendTopic(
            name=topic,
            start_date=start_date_str,
            end_date=end_date_str,
            total_mentions=total,
            peak_week=peak_week,
            peak_count=peak_count
        ))
    
    # Filter time series to only include top topics
    filtered_time_series = {
        topic: time_series[topic]
        for topic, _, _, _ in top_topics_data
    }
    
    logger.info(f"Trend analysis complete: {len(top_topics)} top topics identified")
    
    return TrendAnalysis(
        analysis_date=end_date.isoformat(),
        top_topics=top_topics,
        time_series=filtered_time_series,
        period_type=period_type
    )
