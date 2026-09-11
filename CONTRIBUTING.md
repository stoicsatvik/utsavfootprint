# Contributing

Utsav Footprint is open source because environmental accountability should be inspectable, forkable and reproducible.

## Ground rules

1. Never fabricate sensor precision or source provenance.
2. Do not add unauthorised camera discovery, credential bypass, face recognition or covert tracking.
3. Keep raw personal data out of the core sensor model.
4. New source adapters must preserve source URL/ID, acquisition time and uncertainty.
5. Add tests when changing fusion, deduplication or confidence logic.
6. Prefer open standards and replaceable components over vendor lock-in.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,cctv]'
ruff check src tests scripts
pytest -q
```

Small focused pull requests are easier to review than heroic 8,000-line code avalanches. Computers may enjoy those. Maintainers generally do not.
