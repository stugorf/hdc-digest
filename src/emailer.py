import os
import sys
import html
import traceback
from datetime import datetime, timezone
from typing import cast
import resend
from .digest import DigestResult


def _escape_html(text: str) -> str:
    """Escape HTML entities to prevent XSS attacks."""
    return html.escape(text)


def render_email(digest: DigestResult) -> str:
    """Render digest as HTML email content."""
    html_content = [f"<h1>HDC Daily Digest</h1><p>Date: {_escape_html(digest.date_utc)}</p>"]

    total = 0
    for sec in digest.sections:
        if not sec.items:
            continue
        html_content.append(f"<h2>{_escape_html(sec.name)}</h2>")
        for item in sec.items:
            total += 1
            # Escape all user-provided content
            title = _escape_html(item.title)
            url = _escape_html(item.url)
            published = _escape_html(item.published_date) if item.published_date else "—"
            publisher = _escape_html(item.publisher)
            summary = _escape_html(item.summary)
            
            html_content.append(f"""
              <h3><a href="{url}">{title}</a></h3>
              <p><b>Published:</b> {published} | {publisher}</p>
              <p>{summary}</p>
              <hr/>
            """)

    if total == 0:
        html_content.append("<p>No new items today.</p>")

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