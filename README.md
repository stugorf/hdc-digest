# HDC Digest

Automated email digests for Hyperdimensional Computing (HDC), hypervectors, and Vector Symbolic Architectures (VSA): a **daily digest** of recent items and a **weekly trends** summary with charts.

## Features

- **Daily digest** — Scheduled via GitHub Actions. Three searches (Papers, News, Blogs), quality gate, deduplication, HTML email via Resend.
- **Weekly trends** — Analyzes the SQLite archive for top topics, builds a trend chart (weeks/months/years), and sends a summary email on Sundays.
- **Local tools** — Justfile recipes for run, preview, seed sample data, and database queries.

## Component diagram

```mermaid
flowchart TB
    subgraph external["External"]
        GH_DAILY["GitHub Actions\n(daily cron)"]
        GH_WEEKLY["GitHub Actions\n(weekly cron)"]
        OPENAI["OpenAI Agents\n(web search)"]
        RESEND["Resend\n(email API)"]
    end

    subgraph entry["Entry points"]
        RUN["run.py\nDaily digest"]
        TRENDS_RUN["trends_run.py\nWeekly trends"]
    end

    subgraph core["Core logic"]
        DIGEST["digest.py\nSearch, quality gate,\ntheme synthesis"]
        TRENDS["trends.py\nTopic extraction,\ntime series, top N"]
    end

    subgraph data["Data & I/O"]
        STORE["store.py\nSQLite (items)"]
        EMAILER["emailer.py\nDaily HTML, send,\nerror email"]
        TRENDS_EMAIL["trends_emailer.py\nChart, trends HTML,\nsend"]
    end

    subgraph cli["CLI & dev"]
        QUERY["query.py\nstats, list, show,\ndate-range"]
        SEED["seed_sample_data.py\nSample items for testing"]
    end

    GH_DAILY --> RUN
    GH_WEEKLY --> TRENDS_RUN
    RUN --> DIGEST
    RUN --> STORE
    RUN --> EMAILER
    DIGEST --> OPENAI
    TRENDS_RUN --> TRENDS
    TRENDS_RUN --> TRENDS_EMAIL
    TRENDS --> STORE
    TRENDS_EMAIL --> RESEND
    EMAILER --> RESEND
    QUERY --> STORE
    SEED --> STORE
```

## Workflow diagrams

### Daily digest workflow

Runs every day at 15:00 UTC (~7am Pacific). Fetches new items, deduplicates, saves to DB, and sends one email.

```mermaid
flowchart LR
    A[Trigger] --> B[run.py]
    B --> C[digest.run_digest]
    C --> D[Web search × 3\nPapers, News, Blogs]
    D --> E[Quality gate\nper section]
    E --> F[Theme synthesis]
    F --> G[load_seen_urls]
    G --> H[filter_new]
    H --> I[save_items]
    I --> J[render_email]
    J --> K[send_digest_email]
    K --> L[Resend]
```

### Weekly trends workflow

Runs every Sunday at 16:00 UTC (8am PST). Reads from DB, computes trends and chart, sends one email.

```mermaid
flowchart LR
    A[Trigger] --> B[trends_run.py]
    B --> C[analyze_trends]
    C --> D[Query items\nby date range]
    D --> E[Extract topics\nagent or keywords]
    E --> F[Build time series\nper topic]
    F --> G[Top N topics\nstart/stop dates]
    G --> H[Generate chart\nmatplotlib]
    H --> I[render_trends_email]
    I --> J[send_trends_email]
    J --> K[Resend]
```

## Run locally

```bash
# Install (use uv recommended)
uv sync
# or: pip install -e .

# Environment
export OPENAI_API_KEY=...
export RESEND_API_KEY=...
export EMAIL_TO=you@example.com
export EMAIL_FROM="HDC Digest <digest@yourdomain.com>"
# Or use a .env file; just recipes load it automatically.
```

**Daily digest**

```bash
just run                  # Run and send email
just dry-run              # Run, save to DB, no email
just preview              # Run and open HTML preview in browser
```

**Weekly trends**

```bash
just trends               # Analyze and send email
just trends-dry-run       # Analyze, no email
just trends-preview       # Analyze and open preview in browser
```

**Database**

```bash
just seed                 # Seed sample data for testing
just stats                # Database statistics
just list                 # Recent items
just date-range 2025-01-01 2025-02-01
```

See `just help` or `just --list` for all commands.

## Schedules (GitHub Actions)

| Workflow        | Schedule (UTC) | Local (Pacific)   |
|----------------|----------------|------------------|
| Daily digest   | 15:00 daily    | ~7am             |
| Weekly trends  | 16:00 Sundays  | 8am PST (Sunday) |

Both workflows support **Run workflow** from the Actions tab for manual runs.

## License

See repository.
