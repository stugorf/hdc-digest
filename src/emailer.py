import os
import sys
import html
import traceback
from datetime import datetime, timezone
from typing import cast
import resend
from .digest import DigestItem, DigestResult


def _escape_html(text: str) -> str:
    """Escape HTML entities to prevent XSS attacks."""
    return html.escape(text)


def _render_item(
    item: DigestItem,
    show_quality: bool = False,
) -> str:
    """Render a single digest item as HTML. Optionally include quality gate info."""
    title = _escape_html(item.title)
    url = (item.url or "").strip()
    if url:
        url_escaped = _escape_html(url)
        title_block = f"<h3><a href=\"{url_escaped}\">{title}</a></h3>"
    else:
        title_block = f"<h3>{title}</h3>"
    published = _escape_html(item.published_date) if (item.published_date and item.published_date.strip()) else "—"
    publisher = _escape_html(item.publisher or "")
    summary = _escape_html(item.summary) if (item.summary and item.summary.strip()) else "(No summary)"
    parts = [
        title_block,
        f"<p><b>Published:</b> {published} | {publisher}</p>",
        f"<p>{summary}</p>",
    ]
    if show_quality and item.quality:
        q = item.quality
        verdict = _escape_html(q.get("verdict", ""))
        confidence = _escape_html(q.get("confidence", ""))
        reason = _escape_html(q.get("reason", ""))
        parts.append(
            f"<p><b>Quality gate:</b> {verdict} ({confidence}) — {reason}</p>"
        )
    parts.append("<hr/>")
    return "\n              ".join(parts)


def render_email(digest: DigestResult) -> str:
    """Render digest as HTML email content. Kept items first, then dropped items for review."""
    html_content = [f"<h1>HDC Daily Digest</h1><p>Date: {_escape_html(digest.date_utc)}</p>"]

    # --- Kept items (main digest) ---
    total = 0
    for sec in digest.sections:
        if not sec.items:
            continue
        html_content.append(f"<h2>{_escape_html(sec.name)}</h2>")
        for item in sec.items:
            total += 1
            html_content.append(_render_item(item, show_quality=False))

    if total == 0:
        html_content.append("<p>No new items today.</p>")

    # --- Dropped items (for review) ---
    total_dropped = sum(len(sec.dropped_items) for sec in digest.sections)
    if total_dropped > 0:
        html_content.append("<h2>Dropped items (for review)</h2>")
        html_content.append(
            "<p>Items below were found by search but did not pass the HDC relevance quality gate. "
            "Included so you can review what was filtered and evaluate the gate.</p>"
        )
        for sec in digest.sections:
            if not sec.dropped_items:
                continue
            html_content.append(f"<h3>{_escape_html(sec.name)}</h3>")
            for item in sec.dropped_items:
                html_content.append(_render_item(item, show_quality=True))

    return "".join(html_content)


def send_digest_email(digest: DigestResult) -> None:
    """Send digest email via Resend API."""
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
    params = {
        "from": email_from,
        "to": [email_to],
        "subject": f"HDC Daily Digest — {digest.date_utc}",
        "html": render_email(digest),
    }
    
    # Type cast to satisfy type checker - dict is compatible with SendParams at runtime
    resend.Emails.send(cast(resend.Emails.SendParams, params))


def send_error_email(error: Exception, context: str = "") -> None:
    """Send error notification email via Resend API."""
    # Validate required environment variables
    api_key = os.environ.get("RESEND_API_KEY")
    email_from = os.environ.get("EMAIL_FROM")
    email_to = os.environ.get("EMAIL_TO")
    
    if not api_key:
        # Can't send email if API key is missing - log to stderr instead
        print(f"ERROR: Cannot send error email - RESEND_API_KEY missing. Original error: {error}", file=sys.stderr)
        return
    if not email_from:
        print(f"ERROR: Cannot send error email - EMAIL_FROM missing. Original error: {error}", file=sys.stderr)
        return
    if not email_to:
        print(f"ERROR: Cannot send error email - EMAIL_TO missing. Original error: {error}", file=sys.stderr)
        return
    
    resend.api_key = api_key
    
    # Format error details
    error_type = type(error).__name__
    error_message = str(error)
    error_traceback = traceback.format_exc()
    date_str = datetime.now(timezone.utc).date().isoformat()
    
    # Build HTML error email
    html_content = f"""
    <h1>HDC Daily Digest — Error</h1>
    <p><b>Date:</b> {_escape_html(date_str)}</p>
    <p><b>Status:</b> <span style="color: red;">Failed</span></p>
    """
    
    if context:
        html_content += f"<p><b>Context:</b> {_escape_html(context)}</p>"
    
    html_content += f"""
    <hr/>
    <h2>Error Details</h2>
    <p><b>Error Type:</b> {_escape_html(error_type)}</p>
    <p><b>Error Message:</b> {_escape_html(error_message)}</p>
    <hr/>
    <h2>Traceback</h2>
    <pre style="background-color: #f5f5f5; padding: 10px; overflow-x: auto;">{_escape_html(error_traceback)}</pre>
    """
    
    # Construct email parameters
    params = {
        "from": email_from,
        "to": [email_to],
        "subject": f"HDC Daily Digest — Error ({date_str})",
        "html": html_content,
    }
    
    try:
        resend.Emails.send(cast(resend.Emails.SendParams, params))
    except Exception as email_error:
        # If sending error email fails, log to stderr
        print(f"ERROR: Failed to send error notification email: {email_error}", file=sys.stderr)
        print(f"Original error: {error}", file=sys.stderr)