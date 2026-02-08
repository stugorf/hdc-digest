import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from agents import Agent, Runner, WebSearchTool


# -----------------------------
# Data models
# -----------------------------

@dataclass
class DigestItem:
    title: str
    published_date: str
    url: str
    summary: str
    source_type: str
    publisher: str
    quality: Optional[Dict[str, str]] = None


@dataclass
class DigestSection:
    name: str
    query: str
    items: List[DigestItem]


@dataclass
class DigestResult:
    date_utc: str
    top_themes: List[str]
    sections: List[DigestSection]


# -----------------------------
# Agent
# -----------------------------

SYSTEM_PROMPT = """
You are an expert research assistant focused on Hyperdimensional Computing (HDC).

HDC includes:
- Hypervectors
- Vector Symbolic Architectures (VSA)
- HRR, SPA, MAP, binding, bundling, permutation
- HDC hardware or neuromorphic implementations

It does NOT include:
- Generic "high-dimensional data"
- Ordinary embeddings or vector databases unless explicitly HDC/VSA
"""

def build_agent() -> Agent:
    return Agent(
        name="HDC Digest Agent",
        instructions=SYSTEM_PROMPT,
        tools=[WebSearchTool()],
        model="gpt-5-mini",
    )


# -----------------------------
# Section search
# -----------------------------

def _run_section(agent: Agent, name: str, query: str, days_back: int, max_items: int) -> Dict[str, Any]:
    prompt = f"""
SECTION: {name}

Run a web search for the query below.

QUERY:
{query}

Return ONLY valid JSON:
{{
  "name": "{name}",
  "query": "{query}",
  "items": [
    {{
      "title": "...",
      "published_date": "YYYY-MM-DD or empty",
      "url": "...",
      "summary": "2–4 factual sentences",
      "source_type": "{'paper' if name=='Papers' else ('news' if name=='News' else 'blog')}",
      "publisher": "publisher or empty"
    }}
  ]
}}

Rules:
- Focus on last {days_back} days
- Max {max_items} items
- Drop weak or tangential matches
- JSON only
"""
    result = Runner.run_sync(agent, prompt)
    return json.loads(result.final_output)


# -----------------------------
# Quality gate
# -----------------------------

def _quality_gate_section(agent: Agent, section: Dict[str, Any]) -> Dict[str, Any]:
    prompt = f"""
Verify each item is truly about Hyperdimensional Computing (HDC) / VSA / hypervectors.

Mark:
- KEEP if clearly HDC/VSA
- DROP otherwise

Return ONLY JSON:
{{
  "name": "{section['name']}",
  "query": "{section['query']}",
  "items": [
    {{
      "title": "...",
      "published_date": "...",
      "url": "...",
      "summary": "...",
      "source_type": "...",
      "publisher": "...",
      "quality": {{
        "verdict": "KEEP|DROP",
        "confidence": "high|medium|low",
        "reason": "one short sentence"
      }}
    }}
  ]
}}

INPUT:
{json.dumps(section)}
"""
    result = Runner.run_sync(agent, prompt)
    gated = json.loads(result.final_output)

    gated["items"] = [
        it for it in gated.get("items", [])
        if it.get("quality", {}).get("verdict") == "KEEP"
    ]
    return gated


# -----------------------------
# Main digest
# -----------------------------

def run_digest(days_back: int = 3, max_items_per_section: int = 8) -> DigestResult:
    agent = build_agent()

    queries = {
        "Papers": '("hyperdimensional computing" OR hypervector OR "vector symbolic") (paper OR arxiv)',
        "News": '("hyperdimensional computing" OR hypervector OR "vector symbolic") news',
        "Blogs": '("hyperdimensional computing" OR hypervector OR binding bundling) blog'
    }

    raw = [
        _run_section(agent, name, q, days_back, max_items_per_section)
        for name, q in queries.items()
    ]

    gated = [_quality_gate_section(agent, s) for s in raw]

    # Synthesize themes
    synth_prompt = f"""
Summarize the main themes across the sections below.

Return ONLY JSON:
{{
  "date_utc": "YYYY-MM-DD",
  "top_themes": ["...", "..."],
  "sections": {json.dumps(gated)}
}}
"""
    synth = Runner.run_sync(agent, synth_prompt)
    data = json.loads(synth.final_output)

    sections: List[DigestSection] = []
    for s in data["sections"]:
        items = [
            DigestItem(**it)
            for it in s.get("items", [])
        ]
        sections.append(DigestSection(s["name"], s["query"], items))

    return DigestResult(
        date_utc=data.get("date_utc", datetime.now(timezone.utc).date().isoformat()),
        top_themes=data.get("top_themes", []),
        sections=sections,
    )