# HDC Daily Digest Agent

A daily, automated email digest covering Hyperdimensional Computing (HDC),
hypervectors, and Vector Symbolic Architectures (VSA).

## Features
- Scheduled daily via GitHub Actions
- Three focused searches (Papers, News, Blogs)
- Quality gate to remove false positives
- Deduplication across days
- Clean HTML email via Resend

## Run locally
```bash
export OPENAI_API_KEY=...
export RESEND_API_KEY=...
export EMAIL_TO=you@example.com
export EMAIL_FROM="HDC Digest <digest@yourdomain.com>"

pip install -e .
python -m src.run