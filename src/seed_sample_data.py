"""Seed the SQLite database with sample HDC items for local testing."""
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .store import _init_db, _get_db_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Sample items: (title, summary, source_type, publisher, section_name)
# first_seen_date is derived to spread over the last ~52 weeks
SAMPLE_ITEMS = [
    # Papers - binding, VSA, encoding
    (
        "Efficient binding and bundling in vector symbolic architectures",
        "We present a method for binding and bundling hypervectors that reduces memory and improves retrieval. Experiments on symbolic reasoning tasks show significant gains over baseline VSA encodings.",
        "paper",
        "arXiv",
        "Papers",
    ),
    (
        "Hyperdimensional computing for neuromorphic hardware",
        "This paper explores hyperdimensional computing on neuromorphic chips. We use permutation and binding operations to implement one-shot learning with low energy consumption.",
        "paper",
        "IEEE",
        "Papers",
    ),
    (
        "Vector symbolic architectures for graph-structured data",
        "We extend vector symbolic architectures to encode graphs via binding and bundling. Similarity search in the hypervector space recovers approximate graph queries.",
        "paper",
        "NeurIPS",
        "Papers",
    ),
    (
        "Scalable hypervector encoding for language models",
        "Large-scale encoding of text into hypervectors using binding operations. We show that vector symbolic representations can scale to modern NLP benchmarks.",
        "paper",
        "arXiv",
        "Papers",
    ),
    (
        "Energy-efficient HDC classification on FPGA",
        "Hardware acceleration of hyperdimensional computing for classification. Binding and bundling implemented on FPGA with focus on energy efficiency and throughput.",
        "paper",
        "ACM",
        "Papers",
    ),
    (
        "Permutation-based associative memory in VSA",
        "We analyze permutation operations in vector symbolic architectures for associative memory. Binding and bundling with cyclic shifts improve capacity and retrieval.",
        "paper",
        "Elsevier",
        "Papers",
    ),
    (
        "Brain-inspired computing with hypervectors",
        "Neuromorphic implementation of hyperdimensional computing. Binding, bundling, and permutation map naturally to spiking neural networks and reduce power.",
        "paper",
        "Nature Communications",
        "Papers",
    ),
    (
        "Similarity search in high-dimensional symbolic space",
        "Efficient similarity search over bundled hypervectors. We use locality-sensitive hashing adapted to vector symbolic architectures for sublinear retrieval.",
        "paper",
        "ICML",
        "Papers",
    ),
    (
        "HRR and SPA: a unified view of vector symbolic architectures",
        "We unify Holographic Reduced Representations and Semantic Pointer Architecture under a common binding and bundling framework. Encoding and decoding algorithms are compared.",
        "paper",
        "Cognitive Science",
        "Papers",
    ),
    (
        "Hyperdimensional computing for IoT sensor fusion",
        "Binding and bundling of sensor streams into hypervectors for edge classification. Deployed on microcontroller with minimal memory; suitable for scalable IoT.",
        "paper",
        "IEEE IoT",
        "Papers",
    ),
    # News
    (
        "Startup raises funds for hyperdimensional computing chips",
        "A neuromorphic startup focused on vector symbolic architectures and hyperdimensional computing has raised a new round. Their hardware uses binding and bundling for low-power inference.",
        "news",
        "TechCrunch",
        "News",
    ),
    (
        "Research lab announces breakthrough in VSA efficiency",
        "Scientists report improved binding operations for vector symbolic architectures, enabling larger-scale hypervector applications in machine learning and brain-inspired computing.",
        "news",
        "Science Daily",
        "News",
    ),
    (
        "Hyperdimensional computing gains traction in edge AI",
        "Edge AI vendors are adopting hyperdimensional computing for classification and similarity search. Binding and bundling reduce compute and energy on devices.",
        "news",
        "VentureBeat",
        "News",
    ),
    (
        "New open-source library for vector symbolic architectures",
        "A new library supports HRR, SPA, and MAP-style binding and bundling for hyperdimensional computing. Aimed at research and neuromorphic applications.",
        "news",
        "Hacker News",
        "News",
    ),
    (
        "DARPA program explores HDC for robust AI",
        "A defense program is funding hyperdimensional computing and vector symbolic architectures for robust, interpretable AI. Binding operations and similarity search are key focus areas.",
        "news",
        "Defense One",
        "News",
    ),
    # Blogs
    (
        "Introduction to binding and bundling in HDC",
        "A tutorial on binding and bundling in hyperdimensional computing. We walk through encoding, similarity search, and how permutation fits into vector symbolic architectures.",
        "blog",
        "Personal blog",
        "Blogs",
    ),
    (
        "Building a simple VSA in Python",
        "Hands-on implementation of vector symbolic architectures: binding, bundling, and similarity search. Code uses numpy and matches the HRR formalism.",
        "blog",
        "Towards Data Science",
        "Blogs",
    ),
    (
        "Why neuromorphic and hypervector computing fit together",
        "Neuromorphic hardware and hyperdimensional computing both emphasize sparse, distributed representations. Binding and bundling map well to spikes and energy-efficient learning.",
        "blog",
        "Medium",
        "Blogs",
    ),
    (
        "Scaling hypervector encoding to large vocabularies",
        "We scaled binding-based encoding to millions of symbols. Tips on chunking, bundling, and similarity search without blowing up memory.",
        "blog",
        "Personal blog",
        "Blogs",
    ),
    (
        "HDC vs embeddings: when to use vector symbolic architectures",
        "When are hypervectors and binding/bundling better than standard embeddings? We compare retrieval, robustness, and interpretability in vector symbolic setups.",
        "blog",
        "Distill",
        "Blogs",
    ),
]

QUALITY_JSON = json.dumps({
    "verdict": "KEEP",
    "confidence": "high",
    "reason": "Clearly about HDC/VSA or hypervector computing.",
})


def _seed_sample_data() -> int:
    """Insert sample items into the database. Items are spread over the last 52 weeks.
    Returns the number of rows inserted.
    """
    _init_db()
    conn = _get_db_connection()
    try:
        base_date = datetime.now(timezone.utc).date()
        inserted = 0
        # Spread items over the last 52 weeks; repeat some items in different weeks for trend variety
        for i, (title, summary, source_type, publisher, section_name) in enumerate(SAMPLE_ITEMS):
            # Vary first_seen_date: 0 to 51 weeks ago, with some clustering
            weeks_ago = (i * 3 + (i % 5)) % 52
            first_seen = base_date - timedelta(weeks=weeks_ago)
            first_seen_str = first_seen.isoformat()
            url = f"https://example.com/sample/{section_name.lower()}/{i:03d}-{first_seen_str}"
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO items (
                    url, title, published_date, summary, source_type,
                    publisher, section_name, quality_verdict, quality_confidence,
                    quality_reason, quality_json, first_seen_date, last_seen_date, seen_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    url,
                    title,
                    first_seen_str,
                    summary,
                    source_type,
                    publisher,
                    section_name,
                    "KEEP",
                    "high",
                    "Clearly about HDC/VSA.",
                    QUALITY_JSON,
                    first_seen_str,
                    first_seen_str,
                ),
            )
            if cur.rowcount:
                inserted += 1
        conn.commit()
        # Add more items with repeated topics in recent weeks so trends show variation
        extra = [
            (
                "Binding operations in production VSA systems",
                "Case study on binding and bundling in large-scale vector symbolic architectures. Similarity search and encoding best practices.",
                "paper",
                "arXiv",
                "Papers",
            ),
            (
                "Neuromorphic HDC accelerator tape-out",
                "First silicon for a neuromorphic hyperdimensional computing accelerator. Binding and permutation implemented in analog domain.",
                "news",
                "EE Times",
                "News",
            ),
            (
                "Vector symbolic architectures for robotics",
                "Using binding and bundling for sensorimotor representations in robots. Hypervector encoding and similarity search for policy learning.",
                "paper",
                "RSS",
                "Papers",
            ),
            (
                "Hardware survey: HDC and VSA chips",
                "Survey of FPGA and ASIC implementations of hyperdimensional computing. Binding, bundling, and energy efficiency compared.",
                "blog",
                "IEEE Spectrum",
                "Blogs",
            ),
            (
                "MAP architecture: binding and capacity",
                "Analysis of Multiply-Add-Permute (MAP) binding in vector symbolic architectures. Capacity and similarity search under noise.",
                "paper",
                "arXiv",
                "Papers",
            ),
        ]
        for j, (title, summary, source_type, publisher, section_name) in enumerate(extra):
            # Recent weeks only
            weeks_ago = j % 8
            first_seen = base_date - timedelta(weeks=weeks_ago)
            first_seen_str = first_seen.isoformat()
            url = f"https://example.com/sample/extra/{j}-{first_seen_str}"
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO items (
                    url, title, published_date, summary, source_type,
                    publisher, section_name, quality_verdict, quality_confidence,
                    quality_reason, quality_json, first_seen_date, last_seen_date, seen_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    url,
                    title,
                    first_seen_str,
                    summary,
                    source_type,
                    publisher,
                    section_name,
                    "KEEP",
                    "high",
                    "Clearly about HDC/VSA.",
                    QUALITY_JSON,
                    first_seen_str,
                    first_seen_str,
                ),
            )
            if cur.rowcount:
                inserted += 1
        conn.commit()
        return inserted
    finally:
        conn.close()


def main() -> None:
    """Run the seed script."""
    logger.info("Seeding sample data into %s", Path("hdc_digest.db").resolve())
    n = _seed_sample_data()
    logger.info("Inserted %s sample items. Run 'just trends-preview' or 'just stats' to verify.", n)


if __name__ == "__main__":
    main()
