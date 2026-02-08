"""Email rendering and sending for weekly trends digest."""
import base64
import html
import io
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, cast
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import resend

from .trends import TrendAnalysis, TrendTopic, TrendDataPoint


def _escape_html(text: str) -> str:
    """Escape HTML entities to prevent XSS attacks."""
    return html.escape(str(text))


def _generate_trend_chart(analysis: TrendAnalysis, output_path: Optional[Path] = None) -> str:
    """Generate a trend chart and return as base64-encoded image or save to file.
    
    Args:
        analysis: TrendAnalysis object with time series data
        output_path: Optional path to save chart image
    
    Returns:
        Base64-encoded PNG image string for embedding in email
    """
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Prepare data for plotting
    all_dates = set()
    topic_data = {}
    
    for topic, points in analysis.time_series.items():
        if not points:
            continue
        
        dates = []
        counts = []
        
        for point in points:
            try:
                date_obj = datetime.strptime(point.date, "%Y-%m-%d").date()
                dates.append(date_obj)
                counts.append(point.count)
                all_dates.add(date_obj)
            except ValueError:
                continue
        
        if dates:
            topic_data[topic] = (dates, counts)
    
    if not topic_data:
        # No data to plot
        ax.text(0.5, 0.5, 'No trend data available', 
                horizontalalignment='center', verticalalignment='center',
                transform=ax.transAxes, fontsize=14)
        ax.set_xlabel('Time')
        ax.set_ylabel('Mentions')
        ax.set_title('HDC Research Trends')
    else:
        # Plot each topic as a line
        colors = plt.cm.tab20(range(len(topic_data)))
        for (topic, (dates, counts)), color in zip(topic_data.items(), colors):
            # Handle topic start/stop - only plot when active
            topic_obj = next((t for t in analysis.top_topics if t.name == topic), None)
            if topic_obj and topic_obj.end_date:
                # Topic has ended - only plot up to end date
                end_date = datetime.strptime(topic_obj.end_date, "%Y-%m-%d").date()
                filtered_dates = [d for d in dates if d <= end_date]
                filtered_counts = [c for d, c in zip(dates, counts) if d <= end_date]
                if filtered_dates:
                    ax.plot(filtered_dates, filtered_counts, label=topic, 
                           linewidth=2, color=color, marker='o', markersize=3)
            else:
                # Active topic - plot all data
                ax.plot(dates, counts, label=topic, 
                       linewidth=2, color=color, marker='o', markersize=3)
        
        # Format x-axis based on period type
        if analysis.period_type == "week":
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=4))
        elif analysis.period_type == "month":
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            ax.xaxis.set_major_locator(mdates.MonthLocator())
        elif analysis.period_type == "year":
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
            ax.xaxis.set_major_locator(mdates.YearLocator())
        else:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        
        plt.xticks(rotation=45, ha='right')
        ax.set_xlabel('Time')
        ax.set_ylabel('Number of Mentions')
        ax.set_title('HDC Research Trends Over Time', fontsize=16, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
    
    plt.tight_layout()
    
    # Save to buffer or file
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        logger.info(f"Chart saved to {output_path}")
    
    # Also save to buffer for email
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    buffer.close()
    plt.close()
    
    return image_base64


def render_trends_email(analysis: TrendAnalysis, chart_base64: Optional[str] = None) -> str:
    """Render trends analysis as HTML email content.
    
    Args:
        analysis: TrendAnalysis object
        chart_base64: Optional base64-encoded chart image
    
    Returns:
        HTML email content string
    """
    html_content = [
        f"<h1>HDC Weekly Trends Digest</h1>",
        f"<p><b>Analysis Date:</b> {_escape_html(analysis.analysis_date)}</p>",
        f"<p><b>Period Type:</b> {_escape_html(analysis.period_type)}</p>",
        "<hr/>"
    ]
    
    # Top trends table
    if analysis.top_topics:
        html_content.append("<h2>Top Trends</h2>")
        html_content.append(
            '<table style="border-collapse: collapse; width: 100%; margin-bottom: 1rem;">'
        )
        html_content.append(
            "<thead><tr style=\"background: #eee;\">"
            "<th style=\"border: 1px solid #ccc; padding: 6px 8px; text-align: left;\">Topic</th>"
            "<th style=\"border: 1px solid #ccc; padding: 6px 8px; text-align: right;\">Total</th>"
            "<th style=\"border: 1px solid #ccc; padding: 6px 8px; text-align: right;\">Peak</th>"
            "<th style=\"border: 1px solid #ccc; padding: 6px 8px; text-align: left;\">Peak week</th>"
            "<th style=\"border: 1px solid #ccc; padding: 6px 8px; text-align: left;\">Status</th>"
            "</tr></thead><tbody>"
        )
        for topic in analysis.top_topics:
            status = "Active" if topic.end_date is None else f"Ended: {_escape_html(topic.end_date)}"
            html_content.append(
                f"<tr>"
                f"<td style=\"border: 1px solid #ccc; padding: 6px 8px;\">{_escape_html(topic.name)}</td>"
                f"<td style=\"border: 1px solid #ccc; padding: 6px 8px; text-align: right;\">{topic.total_mentions}</td>"
                f"<td style=\"border: 1px solid #ccc; padding: 6px 8px; text-align: right;\">{topic.peak_count}</td>"
                f"<td style=\"border: 1px solid #ccc; padding: 6px 8px;\">{_escape_html(topic.peak_week)}</td>"
                f"<td style=\"border: 1px solid #ccc; padding: 6px 8px;\">{status}</td>"
                f"</tr>"
            )
        html_content.append("</tbody></table>")
        html_content.append("<hr/>")
    
    # Trend chart
    if chart_base64:
        html_content.append("<h2>Trend Chart</h2>")
        html_content.append(
            f'<img src="data:image/png;base64,{chart_base64}" '
            f'alt="Trend Chart" style="max-width: 100%; height: auto;" />'
        )
        html_content.append("<hr/>")
    
    # Summary statistics
    total_topics = len(analysis.top_topics)
    active_topics = sum(1 for t in analysis.top_topics if t.end_date is None)
    html_content.append("<h2>Summary</h2>")
    html_content.append(f"<p>Total topics tracked: {total_topics}</p>")
    html_content.append(f"<p>Active topics: {active_topics}</p>")
    html_content.append(f"<p>Inactive topics: {total_topics - active_topics}</p>")
    
    return "".join(html_content)


# Configure logging
logger = logging.getLogger(__name__)


def send_trends_email(analysis: TrendAnalysis, dry_run: bool = False) -> None:
    """Generate chart, render email, and send weekly trends digest.
    
    Args:
        analysis: TrendAnalysis object
        dry_run: If True, print email instead of sending
    """
    
    # Generate chart
    logger.info("Generating trend chart...")
    chart_base64 = _generate_trend_chart(analysis)
    logger.info("Chart generated successfully")
    
    # Render email
    html_content = render_trends_email(analysis, chart_base64)
    
    if dry_run:
        # Dry run: print email content
        print("=" * 80)
        print("DRY RUN MODE - Email would be sent with the following content:")
        print("=" * 80)
        print(html_content)
        print("=" * 80)
        return
    
    # Validate required environment variables
    api_key = os.environ.get("RESEND_API_KEY")
    email_from = os.environ.get("EMAIL_FROM")
    email_to = os.environ.get("EMAIL_TO")
    
    if not api_key:
        raise ValueError("RESEND_API_KEY environment variable is required")
    if not email_from:
        raise ValueError("EMAIL_FROM environment variable is required")
    if not email_to:
        raise ValueError("EMAIL_TO environment variable is required")
    
    resend.api_key = api_key
    
    # Construct email parameters
    date_str = analysis.analysis_date
    params = {
        "from": email_from,
        "to": [email_to],
        "subject": f"HDC Weekly Trends Digest — {date_str}",
        "html": html_content,
    }
    
    # Type cast to satisfy type checker
    resend.Emails.send(cast(resend.Emails.SendParams, params))
    logger.info("Trends email sent successfully")
