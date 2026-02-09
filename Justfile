# HDC Daily Digest - Justfile
# Task runner for running the digest and querying the database

# Default recipe: show help
default:
    @just --list

# ============================================================================
# Environment & Setup
# ============================================================================

# Install dependencies using uv
setup:
    uv sync

# Install dependencies and verify environment
install: setup
    @echo "Checking environment variables..."
    @test -n "$$OPENAI_API_KEY" || (echo "WARNING: OPENAI_API_KEY not set" && exit 1)
    @test -n "$$RESEND_API_KEY" || (echo "WARNING: RESEND_API_KEY not set" && exit 1)
    @test -n "$$EMAIL_TO" || (echo "WARNING: EMAIL_TO not set" && exit 1)
    @test -n "$$EMAIL_FROM" || (echo "WARNING: EMAIL_FROM not set" && exit 1)
    @echo "Environment check complete"

# ============================================================================
# Running the Digest
# ============================================================================
# Requires OPENAI_API_KEY (in .env or environment). Optional: RESEND_API_KEY,
# EMAIL_FROM, EMAIL_TO for sending email. Load .env from project root if present.

# Run the digest and send email
run days_back="2":
    @if [ -f .env ]; then set -a && . ./.env && set +a; fi; \
    test -n "$$OPENAI_API_KEY" || (echo "OPENAI_API_KEY is not set. Create a .env file or export OPENAI_API_KEY, then run again." && exit 1); \
    uv run python -m src.run --days-back {{days_back}}

# Run the digest in dry-run mode (no email sent)
dry-run days_back="2":
    @if [ -f .env ]; then set -a && . ./.env && set +a; fi; \
    test -n "$$OPENAI_API_KEY" || (echo "OPENAI_API_KEY is not set. Create a .env file or export OPENAI_API_KEY, then run again." && exit 1); \
    uv run python -m src.run --dry-run --days-back {{days_back}}

# Generate daily digest and open email preview in browser (no email sent)
preview days_back="2":
    @if [ -f .env ]; then set -a && . ./.env && set +a; fi; \
    test -n "$$OPENAI_API_KEY" || (echo "OPENAI_API_KEY is not set. Create a .env file or export OPENAI_API_KEY, then run again." && exit 1); \
    uv run python -m src.run --preview --days-back {{days_back}}

# ============================================================================
# Weekly Trends Analysis
# ============================================================================

# Run trends analysis and send weekly email
trends weeks_back="52" top_n="15" period_type="week":
    @if [ -f .env ]; then \
        set -a && source .env && set +a && uv run python -m src.trends_run --weeks-back {{weeks_back}} --top-n {{top_n}} --period-type {{period_type}}; \
    else \
        uv run python -m src.trends_run --weeks-back {{weeks_back}} --top-n {{top_n}} --period-type {{period_type}}; \
    fi

# Run trends analysis in dry-run mode (no email sent)
trends-dry-run weeks_back="52" top_n="15" period_type="week":
    @if [ -f .env ]; then \
        set -a && source .env && set +a && uv run python -m src.trends_run --dry-run --weeks-back {{weeks_back}} --top-n {{top_n}} --period-type {{period_type}}; \
    else \
        uv run python -m src.trends_run --dry-run --weeks-back {{weeks_back}} --top-n {{top_n}} --period-type {{period_type}}; \
    fi

# Generate trends email and open preview in browser (no email sent)
trends-preview weeks_back="52" top_n="15" period_type="week":
    @if [ -f .env ]; then \
        set -a && source .env && set +a && uv run python -m src.trends_run --preview --weeks-back {{weeks_back}} --top-n {{top_n}} --period-type {{period_type}}; \
    else \
        uv run python -m src.trends_run --preview --weeks-back {{weeks_back}} --top-n {{top_n}} --period-type {{period_type}}; \
    fi

# ============================================================================
# Database Queries
# ============================================================================

# Show database statistics
stats:
    @if [ -f .env ]; then \
        set -a && source .env && set +a && uv run python -m src.query stats; \
    else \
        uv run python -m src.query stats; \
    fi

# List recent items (default: 10)
list limit="10":
    @if [ -f .env ]; then \
        set -a && source .env && set +a && uv run python -m src.query list --limit {{limit}}; \
    else \
        uv run python -m src.query list --limit {{limit}}; \
    fi

# List items as JSON
list-json limit="10":
    @if [ -f .env ]; then \
        set -a && source .env && set +a && uv run python -m src.query list --limit {{limit}} --json; \
    else \
        uv run python -m src.query list --limit {{limit}} --json; \
    fi

# List items from a specific section (Papers, News, or Blogs)
list-section section limit="20":
    @if [ -f .env ]; then \
        set -a && source .env && set +a && uv run python -m src.query list --section {{section}} --limit {{limit}}; \
    else \
        uv run python -m src.query list --section {{section}} --limit {{limit}}; \
    fi

# List items by source type
list-by-type type limit="20":
    @if [ -f .env ]; then \
        set -a && source .env && set +a && uv run python -m src.query list --source-type {{type}} --limit {{limit}}; \
    else \
        uv run python -m src.query list --source-type {{type}} --limit {{limit}}; \
    fi

# Show a specific item by URL
show url:
    @if [ -f .env ]; then \
        set -a && source .env && set +a && uv run python -m src.query show --url {{url}}; \
    else \
        uv run python -m src.query show --url {{url}}; \
    fi

# Get items from a date range (format: YYYY-MM-DD)
date-range start end:
    @if [ -f .env ]; then \
        set -a && source .env && set +a && uv run python -m src.query date-range --start {{start}} --end {{end}}; \
    else \
        uv run python -m src.query date-range --start {{start}} --end {{end}}; \
    fi

# ============================================================================
# Development & Quality
# ============================================================================

# Run linting
lint:
    ruff check .

# Format code
format:
    ruff format .

# Run linting and formatting
check: lint format

# Type check (if mypy/pyright configured)
typecheck:
    @echo "Type checking not configured. Install mypy or pyright to enable."

# ============================================================================
# Database Management
# ============================================================================

# Seed database with sample HDC items for local testing (trends, previews)
seed:
    uv run python -m src.seed_sample_data

# Show database file location and size
db-info:
    @if [ -f hdc_digest.db ]; then \
        echo "Database: hdc_digest.db"; \
        ls -lh hdc_digest.db; \
    else \
        echo "Database not found. Run 'just run' or 'just dry-run' to create it."; \
    fi

# Backup the database
db-backup:
    @if [ -f hdc_digest.db ]; then \
        cp hdc_digest.db "hdc_digest.db.backup.$$(date +%Y%m%d_%H%M%S)"; \
        echo "Database backed up"; \
    else \
        echo "Database not found. Nothing to backup."; \
    fi

# ============================================================================
# Utilities
# ============================================================================

# Clean temporary files and caches
clean:
    rm -rf __pycache__ .pytest_cache .ruff_cache .mypy_cache
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Show help message
help:
    @echo "HDC Daily Digest - Available Commands"
    @echo ""
    @echo "Setup:"
    @echo "  just setup          Install dependencies"
    @echo "  just install        Install and verify environment"
    @echo ""
    @echo "Running:"
    @echo "  just run            Run digest and send email"
    @echo "  just dry-run        Run digest without sending email"
    @echo "  just preview        Generate digest and open email preview in browser"
    @echo "  just trends         Run weekly trends analysis and send email"
    @echo "  just trends-dry-run Run trends analysis without sending email"
    @echo "  just trends-preview Generate trends email and open preview in browser"
    @echo ""
    @echo "Database Queries:"
    @echo "  just stats                          Show database statistics"
    @echo "  just list [limit=10]                List recent items"
    @echo "  just list-section <section>         List items from section (Papers/News/Blogs)"
    @echo "  just list-by-type <type>            List items by source type"
    @echo "  just show <url>                     Show specific item"
    @echo "  just date-range <start> <end>       Get items from date range"
    @echo ""
    @echo "Development:"
    @echo "  just lint           Run linter"
    @echo "  just format         Format code"
    @echo "  just check          Run lint and format"
    @echo ""
    @echo "Database:"
    @echo "  just seed           Seed database with sample data for testing"
    @echo "  just db-info        Show database info"
    @echo "  just db-backup      Backup database"
    @echo ""
    @echo "Utilities:"
    @echo "  just clean          Clean temporary files"
    @echo "  just help           Show this help message"
