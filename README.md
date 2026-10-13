# Gold stock-transfer monitor (adapted)

**What changed in this adaptation (Final exercise):**

- **A different question.** The page now asks: *Gold used to move opposite to US real interest rates. Is it
  still priced off them, when did the link break, and who has been buying since?* The title and the first tab
  are built around it.
- **Another dataset, real.** `data/price.csv` is now real data saved in `data/raw/` on 13 Oct 2026: COMEX gold
  front-month futures (GC=F, daily closes from the Yahoo Finance chart API, averaged by month) and the US
  10-year TIPS real yield (FRED `DFII10`, monthly average), Jan 2020 – Sep 2026
  (`python ingest.py --real-price` rebuilds it offline).
- **A new first tab, "Gold vs real rates · real data", with new views:**
  - a scatter of gold against the real yield, one dot per month coloured by year, with the "old rule" line
    fitted on the chosen years;
  - the rolling correlation between monthly changes in gold and in the real yield (is the link still there?);
  - actual price against the old-rule price over time, with the fit years shaded;
  - the monthly gap in $/oz or %;
  - three headline numbers (the old rule's slope, the implied price now, the actual price now).
- **Comparisons work differently.** You choose the years the "old" relationship is fitted on (instead of a
  fixed pre-2022 fit) and the rolling window (12, 24 or 36 months); every chart in the tab recomputes. In the
  holders tab the official-sector ranking compares over 3, 6, 12 or 24 months, in tonnes or as each bank's share
  of all net buying, and the per-bank detail lets you pick the banks.
- **Sample data stays labelled as sample data.** ETF holdings, central-bank purchases, the
  reported-vs-estimated gap and Swiss exports are still the synthetic sample: their tabs are named
  "Holders · sample data" and "Flows · sample data", every panel and KPI tile built on them carries a
  **SAMPLE DATA** badge, and a banner at the top says which data are real. `data/provenance.json` records this.
- **Ready to host:** pinned `requirements.txt`, `requirements-ingest.txt`, `.streamlit/config.toml`,
  `.gitignore`, `.python-version` (3.11). See *Host it* below.

## Run

    pip install -r requirements.txt
    streamlit run app.py              # the data/ CSVs are included, so this runs immediately

To regenerate the data:

    python ingest.py --synthetic      # sample data for every source (overwrites price.csv with sample too)
    python ingest.py --real-price     # then replace the price panel with the real data in data/raw/

## Host it (Streamlit Community Cloud, free)

1. Create a new **public** GitHub repository and upload everything in this folder (keep `data/`).
2. Go to <https://share.streamlit.io>, sign in with GitHub, choose **Create app → Deploy a public app from
   GitHub**, pick the repository, branch `main`, main file `app.py`.
3. Under **Advanced settings** choose Python 3.11, then **Deploy**. The app reads only `data/*.csv`, so it
   needs no secrets or network access.

## Layout

Desktop-first as of this build: `layout="wide"`, capped at 1180 px, side-by-side
rows where continuity is not lost. The phone-first single-column rationale is
recorded in notebook §7 and in the HTML mockup.

## Live data

    python ingest.py --all

`price` (COMEX futures + FRED real yield) works out of the box. `etf`,
`declared`, `gap`, `swiss` raise NotImplementedError with the exact endpoint
and schema to fill in — issuer URLs and the IMF SDMX call are the two pieces
that drift, so they are isolated in `ingest.py` and nowhere else. The app
only ever reads `data/*.csv`; every pull also lands a timestamped vintage in
`data/vintages/` because customs and IMF sources revise silently.

## Files

    app.py                          the dashboard
    design.py                       entity hues, epistemic grammar, events, mine constants
    ingest.py                       one function per source; --synthetic sample generator
    how_the_dashboard_is_built.ipynb  the reasoning: sources, derived series, gestalt, layout
    data/                           CSVs the app reads

Design contract: solid = reported, dashed = estimated; one colour per country
on every panel; the same event rules on every time axis; one bordered region
(the KPI strip); one dominant chart per tab. The notebook records why.
