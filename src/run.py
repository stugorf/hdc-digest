import argparse
import sys
from .digest import run_digest
from .store import load_seen_urls, filter_new, save_items
from .emailer import send_digest_email, send_error_email, render_email

def main():
    """Run digest and send email. Always sends an email (success, no content, or error)."""
    parser = argparse.ArgumentParser(description="Run HDC Daily Digest")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate digest and save to database, but do not send email"
    )
    args = parser.parse_args()
    
    try:
        # Generate digest
        digest = run_digest()

        # Filter out already-seen items
        seen_urls = load_seen_urls()
        digest = filter_new(digest, seen_urls)

        # Save all items (new and existing) to SQLite database with full metadata
        save_items(digest)

        if args.dry_run:
            # Dry run: print email content instead of sending
            print("=" * 80)
            print("DRY RUN MODE - Email would be sent with the following content:")
            print("=" * 80)
            print(render_email(digest))
            print("=" * 80)
            print(f"Total items in digest: {sum(len(s.items) for s in digest.sections)}")
        else:
            # Send digest email (will include "No new items today" if empty)
            send_digest_email(digest)
        
    except Exception as e:
        if args.dry_run:
            # In dry-run mode, just print the error instead of sending email
            print(f"ERROR: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            sys.exit(1)
        else:
            # Send error notification email
            send_error_email(e, context="Failed during digest generation or email sending")
            # Re-raise to ensure workflow fails visibly
            raise

if __name__ == "__main__":
    main()