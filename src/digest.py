import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from agents import Agent, Runner, WebSearchTool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# -----------------------------
# Data models
# -----------------------------

@dataclass
class DigestItem:
    title: str
    published_date: str
    url: str
    summary: str
    source_type: str
    publisher: str
    quality: Optional[Dict[str, str]] = None


@dataclass
class DigestSection:
    name: str
    query: str
    items: List[DigestItem]
    dropped_items: List[DigestItem] = field(default_factory=list)


@dataclass
class DigestResult:
    date_utc: str
    top_themes: List[str]
    sections: List[DigestSection]
    duration_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert DigestResult to a dictionary for JSON serialization."""
        from dataclasses import asdict
        return asdict(self)


# -----------------------------
# Agent
# -----------------------------

SYSTEM_PROMPT = """
You are an expert research assistant focused on Hyperdimensional Computing (HDC).

HDC includes:
- Hypervectors
- Vector Symbolic Architectures (VSA)
- HRR, SPA, MAP, binding, bundling, permutation
- HDC hardware or neuromorphic implementations

It does NOT include:
- Generic "high-dimensional data"
- Ordinary embeddings or vector databases unless explicitly HDC/VSA
"""

def build_agent() -> Agent:
    return Agent(
        name="HDC Digest Agent",
        instructions=SYSTEM_PROMPT,
        tools=[WebSearchTool()],
        model="gpt-5-mini",
    )


# -----------------------------
# JSON extraction helper
# -----------------------------

def _fix_json_string(json_str: str) -> str:
    """
    Attempt to fix common JSON issues like unescaped quotes in string values.
    This is a best-effort fix for malformed JSON from agents.
    """
    # Try to fix unescaped quotes in string values
    # This is a simple heuristic - look for patterns like "text"text" and escape the inner quotes
    import re
    
    # Pattern to find string values: "value"
    # We want to escape quotes that are inside the value but not the delimiters
    def escape_inner_quotes(match):
        full_match = match.group(0)
        # Skip if it's already escaped or if it's a key (has : after it)
        if '\\"' in full_match:
            return full_match
        # Check if this looks like a value (not a key)
        # Keys are followed by :, values are followed by , or } or ]
        return full_match
    
    # More aggressive: try to find and fix unescaped quotes in JSON string values
    # This is tricky, so we'll use a simpler approach: try parsing with different strategies
    
    return json_str


def _extract_json(text: str) -> Dict[str, Any]:
    """
    Extract JSON from agent output, handling markdown code blocks and other formatting.
    """
    original_text = text
    text = text.strip()
    
    # First, try to parse directly
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.debug(f"Direct parse failed: {e}")
        # Try raw_decode which handles trailing content
        try:
            decoder = json.JSONDecoder()
            parsed, idx = decoder.raw_decode(text)
            logger.debug(f"Direct parse succeeded with raw_decode")
            return parsed
        except json.JSONDecodeError:
            pass
        # Try to fix common issues and parse again
        try:
            # Remove any trailing content after the last }
            last_brace = text.rfind('}')
            if last_brace != -1:
                cleaned = text[:last_brace + 1]
                return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
    
    # Try to extract JSON from markdown code blocks
    # Match ```json or ``` followed by JSON content
    json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    matches = re.findall(json_pattern, text, re.DOTALL)
    if matches:
        # For nested JSON, we need to find the matching braces
        for match_start in re.finditer(r'```(?:json)?\s*\{', text, re.DOTALL):
            # Find the matching closing brace
            start_pos = match_start.end() - 1  # Position of the opening {
            brace_count = 0
            i = start_pos
            while i < len(text):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        # Found matching closing brace
                        json_str = text[start_pos:i + 1]
                        try:
                            return json.loads(json_str)
                        except json.JSONDecodeError as e:
                            logger.debug(f"Markdown block parse failed: {e}")
                            break
                i += 1
    
    # Try to find JSON object boundaries by matching braces
    # Look for first { and find its matching }
    start_idx = text.find('{')
    if start_idx != -1:
        brace_count = 0
        for i in range(start_idx, len(text)):
            if text[i] == '{':
                brace_count += 1
            elif text[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    json_str = text[start_idx:i + 1]
                    # Clean up the JSON string - remove any trailing content
                    json_str = json_str.strip()
                    try:
                        # Try using raw_decode which can handle trailing content
                        decoder = json.JSONDecoder()
                        parsed, idx = decoder.raw_decode(json_str)
                        logger.debug(f"Successfully extracted JSON using brace matching with raw_decode")
                        return parsed
                    except json.JSONDecodeError as e:
                        logger.debug(f"raw_decode failed: {e}")
                        # If raw_decode fails, try regular loads
                        try:
                            parsed = json.loads(json_str)
                            logger.debug(f"Successfully extracted JSON using brace matching")
                            return parsed
                        except json.JSONDecodeError as e2:
                            logger.debug(f"Brace matching parse failed: {e2}, JSON string length: {len(json_str)}")
                            logger.debug(f"Problematic JSON (first 500 chars): {json_str[:500]}")
                            
                            # The issue is likely unescaped quotes. Let's try a simple fix:
                            # Replace unescaped quotes inside string values with escaped quotes
                            # This is a heuristic - look for : "text"text" pattern
                            try:
                                # Simple approach: find string values and escape quotes that aren't already escaped
                                # Pattern: find "..." that contains unescaped "
                                # We'll use a state-based approach: track if we're inside a string
                                fixed_chars = []
                                in_string = False
                                escape_next = False
                                i = 0
                                while i < len(json_str):
                                    char = json_str[i]
                                    if escape_next:
                                        fixed_chars.append(char)
                                        escape_next = False
                                    elif char == '\\' and in_string:
                                        fixed_chars.append(char)
                                        escape_next = True
                                    elif char == '"':
                                        if in_string:
                                            # Check if this closes the string (next char is , : } ] or whitespace)
                                            peek_ahead = json_str[i+1:].lstrip()
                                            if peek_ahead and peek_ahead[0] in ',:}]':
                                                # This is a closing quote
                                                fixed_chars.append(char)
                                                in_string = False
                                            else:
                                                # This might be an unescaped quote inside the string
                                                fixed_chars.append('\\"')
                                        else:
                                            # Opening quote
                                            fixed_chars.append(char)
                                            in_string = True
                                    else:
                                        fixed_chars.append(char)
                                    i += 1
                                
                                fixed = ''.join(fixed_chars)
                                parsed = json.loads(fixed)
                                logger.debug(f"Successfully extracted JSON after fixing quotes")
                                return parsed
                            except (json.JSONDecodeError, ValueError, IndexError) as fix_error:
                                logger.debug(f"Quote fixing also failed: {fix_error}")
                                pass
                        
                        # Try to find if there's a valid JSON substring
                        # Sometimes there's trailing text that breaks parsing
                        # Try parsing progressively shorter strings
                        for end_offset in range(1, min(50, len(json_str))):
                            try:
                                shorter = json_str[:-end_offset].rstrip()
                                # Make sure it ends with }
                                if shorter.endswith('}'):
                                    parsed = json.loads(shorter)
                                    logger.debug(f"Successfully extracted JSON by trimming {end_offset} chars")
                                    return parsed
                            except (json.JSONDecodeError, ValueError):
                                continue
                        # Section-style JSON with extra "note" key: extract up to end of "items": []
                        if '"items":' in json_str:
                            items_start = json_str.find('"items":')
                            bracket_open = json_str.find('[', items_start)
                            if bracket_open != -1:
                                depth = 1
                                i = bracket_open + 1
                                while i < len(json_str) and depth > 0:
                                    if json_str[i] == '[':
                                        depth += 1
                                    elif json_str[i] == ']':
                                        depth -= 1
                                    i += 1
                                if depth == 0:
                                    end_items = i - 1
                                    truncated = json_str[: end_items + 1] + '}'
                                    try:
                                        parsed = json.loads(truncated)
                                        logger.debug("Successfully extracted JSON by truncating after items array")
                                        return parsed
                                    except json.JSONDecodeError:
                                        pass
                        break
    
    # Last resort: try to find and extract any JSON-like structure
    # Look for patterns like {"name": ...}
    json_obj_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.findall(json_obj_pattern, text, re.DOTALL)
    for match in matches:
        try:
            parsed = json.loads(match)
            logger.debug(f"Successfully extracted JSON using regex pattern matching")
            return parsed
        except json.JSONDecodeError:
            continue
    
    # If all else fails, raise with helpful error message
    logger.error(f"Failed to extract JSON. Full text length: {len(original_text)}")
    logger.error(f"First 1000 chars: {repr(original_text[:1000])}")
    raise ValueError(
        f"Could not extract valid JSON from agent output. First 500 chars: {original_text[:500]}"
    )


# -----------------------------
# Date filtering
# -----------------------------

def _parse_date(s: Optional[str]) -> Optional[datetime]:
    """Parse YYYY-MM-DD to date; return None if missing or invalid."""
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _is_within_days_back(published_date_str: Optional[str], days_back: int) -> bool:
    """True if no date, or parsed date is within the last days_back days (inclusive of today)."""
    if days_back <= 0:
        return True
    d = _parse_date(published_date_str)
    if d is None:
        return True  # keep items with unknown date
    today = datetime.now(timezone.utc).date()
    cutoff = today - timedelta(days=days_back)
    return d.date() >= cutoff


# -----------------------------
# Field normalization
# -----------------------------

def _normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize item dictionary to match DigestItem field names.
    Handles field name variations from agent output.
    """
    normalized = item.copy()
    
    # Map 'type' to 'source_type' if present
    if 'type' in normalized and 'source_type' not in normalized:
        normalized['source_type'] = normalized.pop('type')
        logger.debug(f"Mapped 'type' -> 'source_type' for item: {normalized.get('title', 'unknown')}")
    
    # Remove any extra fields that aren't part of DigestItem
    allowed_fields = {'title', 'published_date', 'url', 'summary', 'source_type', 'publisher', 'quality'}
    normalized = {k: v for k, v in normalized.items() if k in allowed_fields}
    
    # Ensure all required fields exist with defaults if missing
    required_fields = {
        'title': '',
        'published_date': '',
        'url': '',
        'summary': '',
        'source_type': '',
        'publisher': '',
    }
    
    for field, default in required_fields.items():
        if field not in normalized:
            normalized[field] = default
    
    return normalized


# -----------------------------
# Section search
# -----------------------------

def _run_section(agent: Agent, name: str, query: str, days_back: int, max_items: int) -> Dict[str, Any]:
    logger.info(f"🔍 Searching section: {name}")
    logger.info(f"   Query: {query}")
    
    # Calculate explicit date range for better search precision
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=days_back - 1)  # Include today in the range
    end_date = today
    
    # Papers: instruct agent to also use Google Scholar and arXiv
    search_instruction = (
        "Run a web search and also search Google Scholar (https://scholar.google.com) and arXiv (https://arxiv.org) for academic papers. "
        if name == "Papers" else "Run a web search for the query below. "
    )

    prompt = f"""
SECTION: {name}

{search_instruction}

QUERY:
{query}

Return ONLY valid JSON:
{{
  "name": "{name}",
  "query": "{query}",
  "items": [
    {{
      "title": "exact title of the item",
      "published_date": "YYYY-MM-DD or empty string if unknown",
      "url": "full URL to the item (required; use the actual link from search results)",
      "summary": "2–4 factual sentences describing the content (required for every item)",
      "source_type": "{'paper' if name=='Papers' else ('news' if name=='News' else 'blog')}",
      "publisher": "publisher/site name or empty"
    }}
  ]
}}

Rules:
- Include only items published or posted within the last {days_back} days ({start_date.isoformat()} to {end_date.isoformat()}). If the publish date is unknown, you may include the item (leave published_date empty); if the date is known and older than this window, do not include it.
- Max {max_items} items
- Drop weak or tangential matches
- For every item you must provide: title, url (the real link), and summary. published_date and publisher can be empty if unknown.
- Return only the JSON object with keys name, query, items. Do not add "note" or any other keys.
- JSON only
"""
    section_start = time.time()
    result = Runner.run_sync(agent, prompt)
    section_data = _extract_json(result.final_output)
    section_duration = time.time() - section_start
    
    item_count = len(section_data.get("items", []))
    logger.info(f"✅ Completed section: {name} ({item_count} items found, {section_duration:.2f}s)")
    
    return section_data


# -----------------------------
# Quality gate
# -----------------------------

def _quality_gate_section(agent: Agent, section: Dict[str, Any]) -> Dict[str, Any]:
    section_name = section.get("name", "Unknown")
    initial_count = len(section.get("items", []))
    logger.info(f"🔎 Quality gating section: {section_name} ({initial_count} items)")
    
    prompt = f"""
Verify each item is truly about Hyperdimensional Computing (HDC) / VSA / hypervectors.

Mark:
- KEEP if clearly HDC/VSA
- DROP otherwise

Return ONLY JSON. You must preserve every item exactly as given (same title, url, summary, published_date, source_type, publisher) and only add the "quality" object to each item. Do not omit or shorten any field.

{{
  "name": "{section['name']}",
  "query": "{section['query']}",
  "items": [
    {{
      "title": "(copy from input)",
      "published_date": "(copy from input)",
      "url": "(copy from input)",
      "summary": "(copy from input)",
      "source_type": "(copy from input)",
      "publisher": "(copy from input)",
      "quality": {{
        "verdict": "KEEP|DROP",
        "confidence": "high|medium|low",
        "reason": "one short sentence"
      }}
    }}
  ]
}}

INPUT:
{json.dumps(section)}
"""
    gate_start = time.time()
    result = Runner.run_sync(agent, prompt)
    gated = _extract_json(result.final_output)
    gate_duration = time.time() - gate_start

    # Separate kept and dropped items. Normalize verdict (case-insensitive) so we never
    # lose items: only explicit KEEP is kept; everything else goes to dropped (for review).
    kept_items = []
    dropped_items = []
    for it in gated.get("items", []):
        verdict = (it.get("quality") or {}).get("verdict")
        is_keep = (
            isinstance(verdict, str)
            and str(verdict).strip().upper() == "KEEP"
        )
        if is_keep:
            kept_items.append(it)
        else:
            dropped_items.append(it)
    
    gated["items"] = kept_items
    gated["dropped_items"] = dropped_items
    
    kept_count = len(kept_items)
    dropped_count = len(dropped_items)
    logger.info(f"✅ Quality gate complete: {section_name} ({kept_count} kept, {dropped_count} dropped, {gate_duration:.2f}s)")
    
    return gated


# -----------------------------
# Main digest
# -----------------------------

def run_digest(days_back: int = 1, max_items_per_section: int = 8) -> DigestResult:
    overall_start = time.time()
    logger.info("=" * 80)
    logger.info("🚀 Starting HDC Daily Digest generation")
    logger.info(f"   Days back: {days_back}, Max items per section: {max_items_per_section}")
    logger.info("=" * 80)
    
    logger.info("📦 Building agent...")
    agent = build_agent()
    logger.info("✅ Agent built successfully")

    queries = {
        "Papers": '("hyperdimensional computing" OR hypervector OR "vector symbolic") (paper OR arxiv)',
        "News": '("hyperdimensional computing" OR hypervector OR "vector symbolic") news',
        "Blogs": '("hyperdimensional computing" OR hypervector OR binding bundling) blog'
    }

    logger.info(f"📊 Running searches for {len(queries)} sections...")
    search_start = time.time()
    raw = [
        _run_section(agent, name, q, days_back, max_items_per_section)
        for name, q in queries.items()
    ]
    search_duration = time.time() - search_start
    logger.info(f"✅ All searches completed in {search_duration:.2f}s")

    logger.info("🔎 Running quality gates...")
    gated = [_quality_gate_section(agent, s) for s in raw]
    logger.info("✅ All quality gates completed")

    # Extract dropped items before synthesis (they don't need theme synthesis)
    dropped_by_section = {s["name"]: s.get("dropped_items", []) for s in gated}
    
    # Prepare sections for synthesis (only kept items)
    sections_for_synth = [
        {k: v for k, v in s.items() if k != "dropped_items"}
        for s in gated
    ]

    logger.info("📝 Synthesizing themes...")
    synth_start = time.time()
    synth_prompt = f"""
Summarize the main themes across the sections below.

Return ONLY JSON with exactly these two keys (no other keys, no sections):
{{
  "date_utc": "YYYY-MM-DD",
  "top_themes": ["theme1", "theme2", "..."]
}}

Sections (for context only; do not echo back):
{json.dumps(sections_for_synth, default=str)}
"""
    synth = Runner.run_sync(agent, synth_prompt)
    data = _extract_json(synth.final_output)
    synth_duration = time.time() - synth_start
    logger.info(f"✅ Theme synthesis completed in {synth_duration:.2f}s")

    # Build sections from gated data so url, published_date, summary are preserved.
    # Filter out items with published_date older than days_back (keep items with no date).
    cutoff_date = (datetime.now(timezone.utc).date() - timedelta(days=days_back)).isoformat()
    logger.info(f"📅 Filtering items: only keep published_date >= {cutoff_date} or unknown")
    sections: List[DigestSection] = []
    for s in gated:
        section_name = s["name"]
        kept_raw = [it for it in s.get("items", []) if _is_within_days_back(it.get("published_date"), days_back)]
        items = [DigestItem(**_normalize_item(it)) for it in kept_raw]
        dropped_items = [
            DigestItem(**_normalize_item(it))
            for it in s.get("dropped_items", [])
        ]
        sections.append(DigestSection(section_name, s["query"], items, dropped_items))

    total_duration = time.time() - overall_start
    total_items = sum(len(s.items) for s in sections)
    
    logger.info("=" * 80)
    logger.info(f"✅ Digest generation complete!")
    logger.info(f"   Total duration: {total_duration:.2f}s")
    logger.info(f"   Total items: {total_items}")
    logger.info(f"   Sections: {len(sections)}")
    logger.info("=" * 80)

    return DigestResult(
        date_utc=data.get("date_utc", datetime.now(timezone.utc).date().isoformat()),
        top_themes=data.get("top_themes", []),
        sections=sections,
        duration_seconds=total_duration,
    )