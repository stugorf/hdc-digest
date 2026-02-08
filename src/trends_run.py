"""Entry point for running weekly trends analysis and sending email."""
import argparse
import logging
import sys
import webbrowser
from pathlib import Path
from .trends import analyze_trends
from .trends_emailer import send_trends_email, render_trends_email, _generate_trend_chart
from .emailer import send_error_email

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def main():
    """Run trends analysis and send email."""
    parser = argparse.ArgumentParser(description="Run HDC Weekly Trends Analysis")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate trends analysis and render email, but do not send"
    )
    parser.add_argument(
        "--weeks-back",
        type=int,
        default=52,
        help="Number of weeks to analyze (default: 52)"
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=15,
        help="Number of top topics to include (default: 15)"
    )
    parser.add_argument(
        "--period-type",
        type=str,
        choices=["week", "month", "year"],
        default="week",
        help="Time period type for analysis (default: week)"
    )
    parser.add_argument(
        "--no-agent",
        action="store_true",
        help="Use keyword-based topic extraction instead of agent"
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Generate trends, save email HTML to file and open in browser (implies dry-run)"
    )
    args = parser.parse_args()
    
    try:
        logger.info("Starting trends analysis workflow...")
        
        # Analyze trends
        analysis = analyze_trends(
            weeks_back=args.weeks_back,
            top_n=args.top_n,
            period_type=args.period_type,
            use_agent=not args.no_agent
        )
        
        logger.info(f"Trends analysis complete: {len(analysis.top_topics)} topics identified")
        
        if args.dry_run or args.preview:
            chart_base64 = _generate_trend_chart(analysis)
            html_body = render_trends_email(analysis, chart_base64)
            if args.preview:
                preview_path = Path("trends-preview.html")
                full_html = (
                    '<!DOCTYPE html><html><head><meta charset="UTF-8">'
                    '<meta name="viewport" content="width=device-width, initial-scale=1">'
                    '<title>HDC Weekly Trends – Preview</title>'
                    '</head><body style="font-family: system-ui, sans-serif; max-width: 720px; margin: 0 auto; padding: 1rem;">'
                    + html_body
                    + "</body></html>"
                )
                preview_path.write_text(full_html, encoding="utf-8")
                abs_path = preview_path.resolve()
                logger.info("Wrote %s", abs_path)
                webbrowser.open(abs_path.as_uri())
            else:
                print("=" * 80)
                print("DRY RUN MODE - Email would be sent with the following content:")
                print("=" * 80)
                print(html_body)
                print("=" * 80)
                print(f"Total topics: {len(analysis.top_topics)}")
                print(f"Active topics: {sum(1 for t in analysis.top_topics if t.end_date is None)}")
                print("=" * 80)
        else:
            # Send trends email
            logger.info("Sending trends email...")
            send_trends_email(analysis, dry_run=False)
            logger.info("✅ Trends email sent successfully")
        
    except Exception as e:
        logger.error(f"❌ Error occurred: {e}", exc_info=True)
        if args.dry_run or args.preview:
            # In dry-run mode, just print the error
            print(f"ERROR: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            sys.exit(1)
        else:
            # Send error notification email
            logger.info("Sending error notification email...")
            send_error_email(e, context="Failed during trends analysis or email sending")
            # Re-raise to ensure workflow fails visibly
            raise


if __name__ == "__main__":
    main()
