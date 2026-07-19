# Dashboard screenshot guide

No dashboard screenshots are committed yet. Capture them only after running the app against the committed warehouse and checking visible values.

Recommended files:

- `executive-summary.png`
- `program-actuals.png`
- `weather-normalized.png`
- `methodology-source-map.png`
- `mobile-layout.png`

Before adding an image:

1. Run `pytest` and `python pipeline.py --validate`.
2. Start `streamlit run app.py` from the repository root.
3. Confirm the page states that target data is unavailable where relevant.
4. Use the default dataset and avoid personal or local filesystem information.
5. Record the warehouse commit in the pull-request description.
