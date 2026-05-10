# Key Findings — Joule Ledger

Three non-obvious findings surfaced by the dashboard across six years of EfficiencyOne reporting (2019–2024). Detail and supporting visuals are available in the Power BI model.

---

## Finding 1: Electric programs beat their 2024 target across both energy and demand

In 2024, EfficiencyOne reported **172.8 GWh of electricity savings against a filed target of 156.56 GWh** — a beat of approximately **+10.4%**. Demand savings reached **30.7 MW against a target of 26.42 MW** — a beat of approximately **+16.2%**.

Demand response programs contributed an additional 8.1 MW of available capacity on top of the structural demand savings figure.

Total electric program investment was approximately **$67.1 million**, and an additional **$79.1 million** from Natural Resources Canada was distributed through the Canada Greener Homes Grant and Oil to Heat Pump Affordability programs.

**What the dashboard makes visible:** The Plan vs. Actual page shows the program-by-program contribution to the overall beat. The dominant contributors are the Heat Pump Program (strong uptake driven by federal co-funding) and the Home Energy Assessment program (referral pipeline maturation). Two programs — Commercial HVAC and Small Business — fell short of target, which is masked in the portfolio-level headline.

**Implication for refresh users:** When a new Annual Report is published, the variance page will immediately show which programs drove the aggregate result and which offset it — without re-reading the PDF.

---

## Finding 2: Low-income programs are a structurally significant share of cumulative impact

Cumulatively since 2011, EfficiencyOne reports **$5.6 billion in lifetime energy savings**, of which **$628 million has accrued to low-income homeowners and renters** — roughly **11.2% of the total**.

The equity page traces how this share has evolved year over year. Key observations:
- The low-income share of *annual spend* has grown from approximately 8% (2019) to over 14% (2024), driven by the introduction of Province- and federally-funded streams alongside the DSM-Electric funded programs.
- The dashboard separates DSM-funded electric low-income work from Province- and federally-funded programs, making the funding-source breakdown explicit. This matters because the two streams have different oversight mechanisms and reporting requirements.
- Participant counts in dedicated low-income programs grew 3× over the six-year period, even as the electric savings per participant declined slightly — consistent with deeper weatherization work in more challenging housing stock.

**What the dashboard makes visible:** The Equity lens page shows share-of-spend, share-of-savings, and share-of-participation for low-income programs year by year, disaggregated by funding source.

---

## Finding 3: Program taxonomy drift materially affects long-term trend analysis

Across six reporting years, this project identified **41 distinct program name variants resolving to 28 canonical programs**. Programs have been renamed, bundled together, or split out as new federal funding streams created reporting carve-outs.

Examples of drift observed:
- "Low Income Program" → "Efficiency NS Low-Income" → "Low-Income Efficiency" (same program, three names)
- The Canada Greener Homes Grant and Oil to Heat Pump Affordability programs were co-delivered by EfficiencyOne but reported under federal program names from 2021 onward, creating a structural break in the residential category totals
- "Industrial Efficiency" absorbed what was previously reported as a separate "Process Improvement" sub-program in 2022

**Consequence:** Without the reconciliation table, naïve year-over-year comparisons systematically *overstate* the apparent volatility of individual programs. A program that appears to have grown 400% may simply have been renamed; a program that appears to have vanished may have been merged into another.

**What the dashboard makes visible:** The Methodology page documents every mapping decision and preserves the original names for traceability. Every metric on the Plan vs. Actual page uses the reconciled program_id — so a 2019-to-2024 trend line for "Low-Income Efficiency" is actually comparable.

**Recommendation for future refresh:** When a new Annual Report introduces an unfamiliar program name, check `sql/program_mapping.csv` for a plausible canonical match before adding a new `program_id`. The pipeline will flag unmatched names with `__UNKNOWN__` rather than silently accepting a false new program.
