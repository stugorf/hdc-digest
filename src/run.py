import argparse
import json
import logging
import sys
import webbrowser
from pathlib import Path
from .digest import run_digest
from .store import load_seen_urls, load_seen_dropped_urls, filter_new, save_items
from .emailer import send_digest_email, send_error_email, render_email

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def main():
    """Run digest and send email. Always sends an email (success, no content, or error)."""
    parser = argparse.ArgumentParser(description="Run HDC Daily Digest")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate digest and save to database, but do not send email"
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=2,
        help="Number of days to search back (default: 2, provides overlap to catch late-indexed items)"
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Generate digest, save email HTML to file and open in browser (implies dry-run)"
    )
    args = parser.parse_args()
    
    try:
        # Generate digest
        logger.info("Starting digest workflow...")
        digest = run_digest(days_back=args.days_back)

        # Filter out already-seen items
        logger.info("Filtering already-seen items...")
        seen_urls = load_seen_urls()
        seen_dropped_urls = load_seen_dropped_urls()
        initial_count = sum(len(s.items) for s in digest.sections)
        initial_dropped_count = sum(len(s.dropped_items) for s in digest.sections)
        digest = filter_new(digest, seen_urls, seen_dropped_urls)
        new_count = sum(len(s.items) for s in digest.sections)
        new_dropped_count = sum(len(s.dropped_items) for s in digest.sections)
        logger.info(
            "Filtered kept items: %s -> %s (removed %s duplicates)",
            initial_count,
            new_count,
            initial_count - new_count,
        )
        logger.info(
            "Filtered dropped items: %s -> %s (removed %s duplicates)",
            initial_dropped_count,
            new_dropped_count,
            initial_dropped_count - new_dropped_count,
        )

        # Save all items (new and existing) to SQLite database with full metadata
        logger.info("Saving items to database...")
        save_items(digest)
        logger.info("✅ Items saved to database")

        if args.dry_run or args.preview:
            html_body = render_email(digest)
            if args.preview:
                preview_path = Path("email-preview.html")
                full_html = (
                    '<!DOCTYPE html><html><head><meta charset="UTF-8">'
                    '<meta name="viewport" content="width=device-width, initial-scale=1">'
                    '<title>HDC Daily Digest – Preview</title>'
                    '</head><body style="font-family: system-ui, sans-serif; max-width: 720px; margin: 0 auto; padding: 1rem;">'
                    + html_body
                    + "</body></html>"
                )
                preview_path.write_text(full_html, encoding="utf-8")
                abs_path = preview_path.resolve()
                logger.info("Wrote %s", abs_path)
                webbrowser.open(abs_path.as_uri())
            else:
                # Dry run: print email content instead of sending
                print("=" * 80)
                print("DRY RUN MODE - Email would be sent with the following content:")
                print("=" * 80)
                print(html_body)
                print("=" * 80)
                print(f"Total items in digest: {sum(len(s.items) for s in digest.sections)}")
                print(f"Duration: {digest.duration_seconds:.2f}s")
                print("=" * 80)
            
            if not args.preview:
                # Also output JSON summary with duration
                summary = {
                    "date_utc": digest.date_utc,
                    "duration_seconds": digest.duration_seconds,
                    "total_items": sum(len(s.items) for s in digest.sections),
                    "total_dropped": sum(len(s.dropped_items) for s in digest.sections),
                    "sections": [
                        {
                            "name": s.name,
                            "query": s.query,
                            "item_count": len(s.items),
                            "dropped_count": len(s.dropped_items)
                        }
                        for s in digest.sections
                    ],
                    "top_themes": digest.top_themes
                }
                print("\nJSON Summary:")
                print(json.dumps(summary, indent=2))
                print("\nFull JSON (including dropped items):")
                print(json.dumps(digest.to_dict(), indent=2, default=str))
        else:
            # Send digest email (will include "No new items today" if empty)
            logger.info("Sending digest email...")
            send_digest_email(digest)
            logger.info("✅ Email sent successfully")
        
    except Exception as e:
        logger.error(f"❌ Error occurred: {e}", exc_info=True)
        if args.dry_run or args.preview:
            # In dry-run mode, just print the error instead of sending email
            print(f"ERROR: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            sys.exit(1)
        else:
            # Send error notification email
            logger.info("Sending error notification email...")
            send_error_email(e, context="Failed during digest generation or email sending")
            # Re-raise to ensure workflow fails visibly
            raise

if __name__ == "__main__":
    main()