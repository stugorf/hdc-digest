import argparse
import json
import logging
import sys
from .digest import run_digest
from .store import load_seen_urls, filter_new, save_items
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
        default=1,
        help="Number of days to search back (default: 1, reduces OpenAI costs)"
    )
    args = parser.parse_args()
    
    try:
        # Generate digest
        logger.info("Starting digest workflow...")
        digest = run_digest(days_back=args.days_back)

        # Filter out already-seen items
        logger.info("Filtering already-seen items...")
        seen_urls = load_seen_urls()
        initial_count = sum(len(s.items) for s in digest.sections)
        digest = filter_new(digest, seen_urls)
        new_count = sum(len(s.items) for s in digest.sections)
        logger.info(f"Filtered items: {initial_count} -> {new_count} (removed {initial_count - new_count} duplicates)")

        # Save all items (new and existing) to SQLite database with full metadata
        logger.info("Saving items to database...")
        save_items(digest)
        logger.info("✅ Items saved to database")

        if args.dry_run:
            # Dry run: print email content instead of sending
            print("=" * 80)
            print("DRY RUN MODE - Email would be sent with the following content:")
            print("=" * 80)
            print(render_email(digest))
            print("=" * 80)
            print(f"Total items in digest: {sum(len(s.items) for s in digest.sections)}")
            print(f"Duration: {digest.duration_seconds:.2f}s")
            print("=" * 80)
            
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
            
            # Output full JSON with dropped items
            print("\nFull JSON (including dropped items):")
            print(json.dumps(digest.to_dict(), indent=2, default=str))
        else:
            # Send digest email (will include "No new items today" if empty)
            logger.info("Sending digest email...")
            send_digest_email(digest)
            logger.info("✅ Email sent successfully")
        
    except Exception as e:
        logger.error(f"❌ Error occurred: {e}", exc_info=True)
        if args.dry_run:
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