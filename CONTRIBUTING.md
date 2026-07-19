# Contributing

Joule Ledger prioritizes traceability over headline volume.

## Before opening a pull request

```bash
python -m pip install -r requirements.txt
pytest
python pipeline.py --transform
python pipeline.py --validate
```

## Data changes

- Preserve the original source URL/path and page number whenever available.
- Do not convert a missing value to zero.
- Mark manual entries explicitly and explain them in `docs/etl_design.md`.
- Add or update tests for parser, mapping, schema, and grain changes.
- Recheck every README, finding, and dashboard label affected by the data.

## Claims

Describe only results reproducible from committed sources and the current warehouse. Keep proposals in roadmap sections, and do not call a Power BI model, target comparison, public deployment, or six-year result complete until the corresponding artifact is present and reviewed.
