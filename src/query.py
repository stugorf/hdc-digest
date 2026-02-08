#!/usr/bin/env python3
"""CLI tool for querying the HDC digest database."""
import argparse
import json
import sys
from typing import Optional
from .store import (
    get_all_items,
    get_item_by_url,
    get_items_by_date_range,
    get_statistics,
)


def format_item(item: dict) -> str:
    """Format a single item for display."""
    lines = [
        f"Title: {item['title']}",
        f"URL: {item['url']}",
        f"Section: {item['section_name']} | Type: {item['source_type']}",
        f"Published: {item['published_date'] or 'N/A'} | Publisher: {item['publisher'] or 'N/A'}",
        f"First Seen: {item['first_seen_date']} | Seen {item['seen_count']} time(s)",
        f"Summary: {item['summary']}",
    ]
    if item.get('quality_verdict'):
        lines.append(f"Quality: {item['quality_verdict']} ({item.get('quality_confidence', 'N/A')})")
    return "\n".join(lines)


def cmd_list(args: argparse.Namespace) -> None:
    """List items from the database."""
    items = get_all_items(
        limit=args.limit,
        offset=args.offset,
        section_name=args.section,
        source_type=args.source_type,
        order_by=args.order_by
    )
    
    if args.json:
        print(json.dumps(items, indent=2))
    else:
        if not items:
            print("No items found.")
            return
        
        print(f"Found {len(items)} item(s):\n")
        for i, item in enumerate(items, 1):
            print(f"{'=' * 80}")
            print(f"Item {i}/{len(items)}")
            print(f"{'=' * 80}")
            print(format_item(item))
            print()


def cmd_show(args: argparse.Namespace) -> None:
    """Show a single item by URL."""
    item = get_item_by_url(args.url)
    if not item:
        print(f"Item not found: {args.url}", file=sys.stderr)
        sys.exit(1)
    
    if args.json:
        print(json.dumps(item, indent=2))
    else:
        print(format_item(item))


def cmd_date_range(args: argparse.Namespace) -> None:
    """Get items within a date range."""
    items = get_items_by_date_range(args.start_date, args.end_date)
    
    if args.json:
        print(json.dumps(items, indent=2))
    else:
        if not items:
            print(f"No items found between {args.start_date} and {args.end_date}.")
            return
        
        print(f"Found {len(items)} item(s) between {args.start_date} and {args.end_date}:\n")
        for i, item in enumerate(items, 1):
            print(f"{'=' * 80}")
            print(f"Item {i}/{len(items)}")
            print(f"{'=' * 80}")
            print(format_item(item))
            print()


def cmd_stats(args: argparse.Namespace) -> None:
    """Show database statistics."""
    stats = get_statistics()
    
    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print("Database Statistics")
        print("=" * 80)
        print(f"Total items: {stats.get('total_items', 0)}")
        print()
        
        if stats.get('by_section'):
            print("Items by section:")
            for section, count in stats['by_section'].items():
                print(f"  {section}: {count}")
            print()
        
        if stats.get('by_source_type'):
            print("Items by source type:")
            for source_type, count in stats['by_source_type'].items():
                print(f"  {source_type}: {count}")
            print()
        
        if stats.get('date_range'):
            dr = stats['date_range']
            print(f"Date range: {dr.get('earliest')} to {dr.get('latest')}")


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Query the HDC digest database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List recent items
  %(prog)s list --limit 10

  # List papers only
  %(prog)s list --section Papers

  # Show statistics
  %(prog)s stats

  # Get items from date range
  %(prog)s date-range --start 2026-02-01 --end 2026-02-08

  # Show specific item
  %(prog)s show --url https://example.com/article
        """
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List items from database")
    list_parser.add_argument("--limit", type=int, help="Maximum number of items to return")
    list_parser.add_argument("--offset", type=int, default=0, help="Number of items to skip")
    list_parser.add_argument("--section", choices=["Papers", "News", "Blogs"], help="Filter by section")
    list_parser.add_argument("--source-type", help="Filter by source type (paper, news, blog)")
    list_parser.add_argument(
        "--order-by",
        default="first_seen_date DESC",
        help="SQL ORDER BY clause (default: first_seen_date DESC)"
    )
    list_parser.set_defaults(func=cmd_list)
    
    # Show command
    show_parser = subparsers.add_parser("show", help="Show a single item by URL")
    show_parser.add_argument("--url", required=True, help="URL of the item to show")
    show_parser.set_defaults(func=cmd_show)
    
    # Date range command
    date_parser = subparsers.add_parser("date-range", help="Get items within a date range")
    date_parser.add_argument("--start", dest="start_date", required=True, help="Start date (YYYY-MM-DD)")
    date_parser.add_argument("--end", dest="end_date", required=True, help="End date (YYYY-MM-DD)")
    date_parser.set_defaults(func=cmd_date_range)
    
    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show database statistics")
    stats_parser.set_defaults(func=cmd_stats)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == "__main__":
    main()
