import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Set, List, Optional, Dict, Any
from contextlib import contextmanager

from .digest import DigestResult, DigestItem


DB_PATH = Path("hdc_digest.db")


def _get_db_connection() -> sqlite3.Connection:
    """Get a database connection with proper configuration."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn


def _init_db() -> None:
    """Initialize the database schema if it doesn't exist."""
    conn = _get_db_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                published_date TEXT,
                summary TEXT NOT NULL,
                source_type TEXT NOT NULL,
                publisher TEXT,
                section_name TEXT NOT NULL,
                quality_verdict TEXT,
                quality_confidence TEXT,
                quality_reason TEXT,
                first_seen_date TEXT NOT NULL,
                last_seen_date TEXT NOT NULL,
                seen_count INTEGER DEFAULT 1,
                quality_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_url ON items(url)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_first_seen_date ON items(first_seen_date)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_section_name ON items(section_name)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_source_type ON items(source_type)
        """)
        
        conn.commit()
    finally:
        conn.close()


@contextmanager
def _db_transaction():
    """Context manager for database transactions."""
    conn = _get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def load_seen_urls() -> Set[str]:
    """Load set of URLs that have been seen before."""
    _init_db()
    conn = _get_db_connection()
    try:
        cursor = conn.execute("SELECT url FROM items")
        return {row["url"] for row in cursor.fetchall()}
    finally:
        conn.close()


def filter_new(digest: DigestResult, seen_urls: Set[str]) -> DigestResult:
    """Filter out items that have been seen before."""
    for section in digest.sections:
        section.items = [it for it in section.items if it.url not in seen_urls]
    return digest


def save_items(digest: DigestResult) -> None:
    """Save all items from digest to database with full metadata."""
    _init_db()
    date_str = digest.date_utc
    
    with _db_transaction() as conn:
        for section in digest.sections:
            for item in section.items:
                # Extract quality information
                quality_verdict = None
                quality_confidence = None
                quality_reason = None
                quality_json = None
                
                if item.quality:
                    quality_verdict = item.quality.get("verdict")
                    quality_confidence = item.quality.get("confidence")
                    quality_reason = item.quality.get("reason")
                    quality_json = json.dumps(item.quality)
                
                # Check if URL already exists
                cursor = conn.execute("SELECT url, last_seen_date, seen_count FROM items WHERE url = ?", (item.url,))
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing record
                    conn.execute("""
                        UPDATE items
                        SET title = ?,
                            published_date = ?,
                            summary = ?,
                            source_type = ?,
                            publisher = ?,
                            section_name = ?,
                            quality_verdict = ?,
                            quality_confidence = ?,
                            quality_reason = ?,
                            quality_json = ?,
                            last_seen_date = ?,
                            seen_count = seen_count + 1
                        WHERE url = ?
                    """, (
                        item.title,
                        item.published_date or None,
                        item.summary,
                        item.source_type,
                        item.publisher or None,
                        section.name,
                        quality_verdict,
                        quality_confidence,
                        quality_reason,
                        quality_json,
                        date_str,
                        item.url,
                    ))
                else:
                    # Insert new record
                    conn.execute("""
                        INSERT INTO items (
                            url, title, published_date, summary, source_type,
                            publisher, section_name, quality_verdict,
                            quality_confidence, quality_reason, quality_json,
                            first_seen_date, last_seen_date, seen_count
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """, (
                        item.url,
                        item.title,
                        item.published_date or None,
                        item.summary,
                        item.source_type,
                        item.publisher or None,
                        section.name,
                        quality_verdict,
                        quality_confidence,
                        quality_reason,
                        quality_json,
                        date_str,
                        date_str,
                    ))


# Query functions for accessing past content

def get_all_items(
    limit: Optional[int] = None,
    offset: int = 0,
    section_name: Optional[str] = None,
    source_type: Optional[str] = None,
    order_by: str = "first_seen_date DESC"
) -> List[Dict[str, Any]]:
    """Query items from the database.
    
    Args:
        limit: Maximum number of items to return
        offset: Number of items to skip
        section_name: Filter by section name (e.g., "Papers", "News", "Blogs")
        source_type: Filter by source type (e.g., "paper", "news", "blog")
        order_by: SQL ORDER BY clause (default: newest first)
    
    Returns:
        List of item dictionaries with all fields
    """
    _init_db()
    conn = _get_db_connection()
    try:
        query = "SELECT * FROM items WHERE 1=1"
        params = []
        
        if section_name:
            query += " AND section_name = ?"
            params.append(section_name)
        
        if source_type:
            query += " AND source_type = ?"
            params.append(source_type)
        
        query += f" ORDER BY {order_by}"
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        if offset:
            query += " OFFSET ?"
            params.append(offset)
        
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_item_by_url(url: str) -> Optional[Dict[str, Any]]:
    """Get a single item by URL."""
    _init_db()
    conn = _get_db_connection()
    try:
        cursor = conn.execute("SELECT * FROM items WHERE url = ?", (url,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_items_by_date_range(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """Get items first seen within a date range (YYYY-MM-DD format)."""
    _init_db()
    conn = _get_db_connection()
    try:
        cursor = conn.execute(
            "SELECT * FROM items WHERE first_seen_date >= ? AND first_seen_date <= ? ORDER BY first_seen_date DESC",
            (start_date, end_date)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_statistics() -> Dict[str, Any]:
    """Get statistics about stored items."""
    _init_db()
    conn = _get_db_connection()
    try:
        stats = {}
        
        # Total items
        cursor = conn.execute("SELECT COUNT(*) as count FROM items")
        stats["total_items"] = cursor.fetchone()["count"]
        
        # Items by section
        cursor = conn.execute("""
            SELECT section_name, COUNT(*) as count
            FROM items
            GROUP BY section_name
        """)
        stats["by_section"] = {row["section_name"]: row["count"] for row in cursor.fetchall()}
        
        # Items by source type
        cursor = conn.execute("""
            SELECT source_type, COUNT(*) as count
            FROM items
            GROUP BY source_type
        """)
        stats["by_source_type"] = {row["source_type"]: row["count"] for row in cursor.fetchall()}
        
        # Date range
        cursor = conn.execute("SELECT MIN(first_seen_date) as min_date, MAX(first_seen_date) as max_date FROM items")
        row = cursor.fetchone()
        if row["min_date"]:
            stats["date_range"] = {
                "earliest": row["min_date"],
                "latest": row["max_date"]
            }
        
        return stats
    finally:
        conn.close()
