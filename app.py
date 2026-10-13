"""Gold stock-transfer monitor — desktop build, adapted.

Adaptations (Final exercise):
  - real data for the price panel (COMEX gold futures + FRED real yield, data/raw/), sample data elsewhere,
    every sample panel labelled as sample data (data/provenance.json says which is which)
  - a new view: the monthly premium of the price over its yield-implied level
  - comparisons: the official-sector ranking has a choice of window (3, 6, 12 or 24 months) and of measure
    (tonnes, or share of all net buying), and the per-bank detail lets you pick the banks to compare

Run:  python ingest.py --synthetic   (once, or --all for live data)
      streamlit run app.py

Design contract (reasoning in the companion notebook):
  - solid = reported, dashed = estimated; one colour per country everywhere
  - the same event rules on every time axis; labels only on the dominant charts
  - one bordered region (the KPI strip); whitespace does all other grouping
  - one dominant chart per tab: P1 carries Declared, P4 carries Inferred
"""
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

import design as dz

DATA = Path(__file__).parent / "data"

st.set_page_config(page_title="Gold and real rates",
                   layout="wide", initial_sidebar_state="collapsed")

# ---------------------------------------------------------------- chrome/css --
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400;1,6..72,500&family=Archivo:wght@400;500;600&display=swap');

html, body, [class*="css"], .stMarkdown, p, li {
  font-family: 'Archivo', system-ui, sans-serif;
  font-variant-numeric: tabular-nums;
}
.stApp { background: #fbfbf8; color: #1c1c18; }
.block-container { max-width: 1180px; padding-top: 2.2rem; padding-bottom: 3rem; }
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; }

h1 { font-family: 'Newsreader', serif; font-weight: 500; letter-spacing: -.01em;
     font-size: 2.5rem; margin-bottom: 0; }
h3 { font-family: 'Newsreader', serif; font-style: italic; font-weight: 500;
     font-size: 1.35rem; margin-bottom: 0; }
.stCaption, [data-testid="stCaptionContainer"] { color: #8c8c84; }

/* tabs: underline grammar, gold for the active page */
.stTabs [data-baseweb="tab-list"] { gap: 30px; border-bottom: 1px solid #ecece5; }
.stTabs [data-baseweb="tab"] { font-size: 15px; font-weight: 500; color: #8c8c84;
  padding: 6px 0 10px; background: none; }
.stTabs [aria-selected="true"] { color: #1c1c18; }
.stTabs [data-baseweb="tab-highlight"] { background-color: #a3780a; height: 2px; }
.stTabs [data-baseweb="tab-border"] { background-color: transparent; }

/* KPI strip: the only bordered region on the page */
.kpis { border: 1.5px solid #1c1c18; border-radius: 3px;
  display: grid; grid-template-columns: repeat(6, 1fr); gap: 0 26px;
  padding: 14px 18px 10px; margin: 6px 0 4px; }
.kpi .l { font-size: 11px; color: #8c8c84; line-height: 1.25; }
.kpi .v { font-size: 20px; font-weight: 600; margin-top: 1px; }
.kpi .v small { font-size: 11.5px; font-weight: 500; color: #8c8c84; margin-left: 4px; }
.kpi svg { display: block; margin-top: 4px; }

.grammar { font-size: 12.5px; color: #8c8c84; margin: 2px 0 10px; }
.grammar b { color: #1c1c18; font-weight: 500; }
.masthead { display: flex; justify-content: space-between; align-items: baseline; }
.masthead .d { color: #8c8c84; font-size: 13px; }
.tag { display: inline-block; font-size: 10.5px; font-weight: 600; letter-spacing: .06em;
  text-transform: uppercase; padding: 2px 7px; border-radius: 2px; margin: 2px 0 6px; }
.tag.sample { color: #8a4b0f; background: #f6e7d0; border: 1px solid #e3c9a3; }
.tag.real { color: #2f5d3a; background: #e3efe2; border: 1px solid #bcd6b9; }
.kpi .l .s { color: #8a4b0f; font-weight: 600; }
.status { font-size: 12.5px; color: #5c5c55; background: #f6e7d0; border-left: 3px solid #c98a1b;
  padding: 7px 12px; margin: 6px 0 10px; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------- plotly theme --
pio.templates["ledger"] = go.layout.Template(layout=dict(
    paper_bgcolor=dz.PAPER, plot_bgcolor=dz.PAPER,
    font=dict(family="Archivo, system-ui, sans-serif", color=dz.INK, size=13),
    margin=dict(l=10, r=64, t=34, b=10), showlegend=False,
    xaxis=dict(showgrid=False, ticks="outside", tickcolor=dz.GHOST,
               linecolor=dz.GHOST),
    yaxis=dict(gridcolor="#efefe8", zeroline=False, side="right",
               tickformat=","),
    hoverlabel=dict(bgcolor=dz.PAPER, bordercolor=dz.GHOST,
                    font=dict(family="Archivo, system-ui, sans-serif",
                              color=dz.INK, size=12)),
))
pio.templates.default = "ledger"

# ------------------------------------------------------------------ loading --
@st.cache_data(ttl=3600)
def load(name: str, dates=("date",)) -> pd.DataFrame:
    return pd.read_csv(DATA / f"{name}.csv", parse_dates=list(dates))

try:
    price = load("price")
    etf = load("etf")
    declared = load("declared")
    gap = load("gap", dates=("quarter_end",))
    swiss = load("swiss")
except FileNotFoundError:
    st.error("No data found. Run `python ingest.py --synthetic` first.")
    st.stop()

import json
_prov_file = DATA / "provenance.json"
PROV = json.loads(_prov_file.read_text()) if _prov_file.exists() else {}

def is_sample(name: str) -> bool:
    """Anything not explicitly recorded as real is treated as sample data."""
    return PROV.get(name, {}).get("kind") != "real"

def tag(*names: str) -> None:
    """Badge under a panel title: SAMPLE DATA if any input is sample, REAL DATA otherwise."""
    if any(is_sample(n) for n in names):
        st.markdown('<span class="tag sample">Sample data · synthetic, for illustration only</span>',
                    unsafe_allow_html=True)
    else:
        st.markdown('<span class="tag real">Real data</span>', unsafe_allow_html=True)

asof = {"price": price.date.max(), "etf": etf.date.max(),
        "declared": declared.date.max(), "gap": gap.quarter_end.max(),
        "swiss": swiss.date.max()}
fmt = lambda t: pd.Timestamp(t).strftime("%b %y")

# --------------------------------------------------------------- helpers -----
def events(fig, label: bool):
    for i, (d, t) in enumerate(dz.EVENTS):
        fig.add_vline(x=d, line_color=dz.GHOST, line_width=1)
        if label:
            fig.add_annotation(x=d, y=1.03 + 0.075 * (i % 2), yref="paper",
                               text=t, showarrow=False,
                               font=dict(size=11, color=dz.FAINT))

def endlabel(fig, x, y, text, color=dz.FAINT):
    fig.add_annotation(x=x, y=y, text=text, showarrow=False, xanchor="left",
                       xshift=8, font=dict(size=12, color=color))

def chart(fig, h):
    fig.update_layout(height=h)
    st.plotly_chart(fig, width="stretch",
                    config={"displayModeBar": False})

def spark(vals, color, w=76, h=20):
    lo, hi = min(vals), max(vals) + 1e-9
    pts = " ".join(f"{2 + (w-4)*i/(len(vals)-1):.1f},"
                   f"{h-2 - (h-4)*(v-lo)/(hi-lo):.1f}" for i, v in enumerate(vals))
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<polyline points="{pts}" fill="none" stroke="{color}" '
            f'stroke-width="1.6" stroke-linejoin="round"/></svg>')

# ------------------------------------------------------------- derived nums --
t12 = (declared[declared.date > asof["declared"] - pd.DateOffset(months=12)]
       .groupby("country").net_purchases_t.sum().sort_values(ascending=False))
top_buy, top_sell = t12.index[0], t12.index[-1]
east_m = (swiss[swiss.destination.isin(["China + HK", "India", "Turkey"])]
          .groupby("date").tonnes.sum())
all_last = swiss[swiss.date == asof["swiss"]].tonnes.sum()
gap_res = (gap.wgc_estimate_t - gap.imf_reported_t)
p_now, p_prev = price.price_usd_oz.iloc[-1], price.price_usd_oz.iloc[-2]
e_now, e_prev = etf.tonnes.iloc[-1], etf.tonnes.iloc[-2]
china12 = declared[declared.country == top_buy].net_purchases_t.tail(12)
russia12 = declared[declared.country == top_sell].net_purchases_t.tail(12)

# ----------------------------------------------------------------- masthead --
st.markdown(f"""
<div class="masthead"><h1>Gold and real rates: did the link break?</h1>
<span class="d">data to {pd.Timestamp(asof['price']).strftime('%B %Y')}</span></div>
""", unsafe_allow_html=True)
st.caption("Gold used to move opposite to US real interest rates. Is it still priced off them, when did "
           "the link break, and who has been buying since?")
_real = [n for n in ["price", "etf", "declared", "gap", "swiss"] if not is_sample(n)]
_samp = [n for n in ["price", "etf", "declared", "gap", "swiss"] if is_sample(n)]
_names = {"price": "price and real yield", "etf": "ETF holdings", "declared": "central-bank purchases",
          "gap": "reported-vs-estimated gap", "swiss": "Swiss exports"}
st.markdown('<div class="status"><b>Mixed data.</b> '
            + (f"Real: {', '.join(_names[n] for n in _real)}. " if _real else "")
            + (f"<b>Sample data</b> (synthetic, generated by <code>ingest.py --synthetic</code>, not real figures): "
               f"{', '.join(_names[n] for n in _samp)}. Panels and tiles built on sample data are marked "
               f"<span class='tag sample' style='margin:0'>sample</span>." if _samp else "")
            + '</div>', unsafe_allow_html=True)

KPIS = [
    ("price, $/oz", f"{p_now:,.0f}", f"{p_now/p_prev-1:+.1%} m/m",
     spark(price.price_usd_oz.tail(12).tolist(), dz.GOLD)),
    ("GLD + IAU", f"{e_now:,.0f} t", f"{e_now-e_prev:+.0f} t m/m",
     spark(etf.tonnes.tail(12).tolist(), dz.hue("West"))),
    ("gap, latest qtr", f"+{gap_res.iloc[-1]:,.0f} t", "unreported",
     spark(gap_res.tail(8).tolist(), dz.GOLD)),
    ("top buyer, 12m", top_buy, f"+{t12.iloc[0]:,.0f} t",
     spark(china12.tolist(), dz.hue(top_buy))),
    ("top seller, 12m", top_sell, f"{t12.iloc[-1]:,.0f} t",
     spark(russia12.tolist(), dz.hue(top_sell))),
    (f"Swiss → east, {fmt(asof['swiss'])}", f"{east_m.iloc[-1]:,.0f} t",
     f"of {all_last:,.0f} t out",
     spark(east_m.tail(12).tolist(), dz.hue("China"))),
]
KPI_SOURCE = ["price", "etf", "gap", "declared", "declared", "swiss"]
KPIS = [(l + (' <span class="s">· sample</span>' if is_sample(src) else ""), v, s_, sp)
        for (l, v, s_, sp), src in zip(KPIS, KPI_SOURCE)]
tiles = "".join(f'<div class="kpi"><div class="l">{l}</div>'
                f'<div class="v">{v}<small>{s}</small></div>{sp}</div>'
                for l, v, s, sp in KPIS)
st.markdown(f'<div class="kpis">{tiles}</div>', unsafe_allow_html=True)
st.markdown('<p class="grammar"><b>Solid</b> marks reported series, '
            '<b>dashed</b> marks estimates. Each country keeps one colour on '
            'every panel.</p>', unsafe_allow_html=True)

tabR, tabD, tabI = st.tabs(["Gold vs real rates · real data", "Holders · sample data", "Flows · sample data"])

# ====================================================== GOLD vs REAL RATES ====
with tabR:
    import numpy as np
    years = sorted(price.date.dt.year.unique())
    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        fit = st.select_slider("Fit the 'old' relationship on these years", options=years,
                               value=(years[0], 2021), key="fit_years")
    with c2:
        roll = st.radio("Rolling window for the link", [12, 24, 36], index=1, horizontal=True,
                        format_func=lambda m: f"{m} months", key="roll")
    base = price[price.date.dt.year.between(*fit)]
    b, a = np.polyfit(base.real_yield_pct, base.price_usd_oz, 1) if len(base) >= 6 else (np.nan, np.nan)
    pr = price.assign(implied=a + b * price.real_yield_pct)
    pr["premium"] = pr.price_usd_oz - pr.implied
    pr["share"] = (pr.price_usd_oz / pr.implied - 1) * 100
    pr["year"] = pr.date.dt.year.astype(str)
    pr["in_fit"] = pr.date.dt.year.between(*fit)
    if len(base) < 6:
        st.info("Pick a fit period with at least six months.")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric(f"Old rule ({fit[0]}–{fit[1]})", f"{b:+,.0f} $/oz",
                  "per +1 point of real yield", delta_color="off", delta_arrow="off")
        m2.metric(f"Implied price, {fmt(asof['price'])}", f"{pr.implied.iloc[-1]:,.0f} $/oz",
                  f"at a {pr.real_yield_pct.iloc[-1]:.2f}% real yield", delta_color="off", delta_arrow="off")
        m3.metric(f"Actual price, {fmt(asof['price'])}", f"{pr.price_usd_oz.iloc[-1]:,.0f} $/oz",
                  f"{pr.share.iloc[-1]:+,.0f}% vs the old rule", delta_color="off", delta_arrow="off")

        left, right = st.columns([3, 2], gap="large")
        with left:
            st.subheader("Gold against the real interest rate")
            st.caption("Each dot is a month. The dashed line is the relationship in the fit years: "
                       "the higher the real yield, the lower the price.")
            tag("price")
            yr = sorted(pr.year.unique())
            ramp = ["#e9dcb4", "#dcc88a", "#cdb062", "#b8953a", "#a3780a", "#7d5c08", "#4f3a05"]
            cols = {y: ramp[min(i, len(ramp) - 1)] for i, y in enumerate(yr)}
            f = go.Figure()
            f.add_trace(go.Scatter(x=pr.real_yield_pct, y=pr.price_usd_oz, mode="lines",
                line=dict(color=dz.GHOST, width=1), hoverinfo="skip", showlegend=False))
            for y in yr:
                d = pr[pr.year == y]
                f.add_trace(go.Scatter(x=d.real_yield_pct, y=d.price_usd_oz, mode="markers", name=y,
                    marker=dict(color=cols[y], size=9, line=dict(color=dz.INK if d.in_fit.all() else dz.PAPER,
                                                                  width=1.2)),
                    hovertemplate="%{text}<br>real yield %{x:.2f}%<br>price %{y:,.0f} $/oz<extra></extra>",
                    text=d.date.dt.strftime("%b %Y")))
            xs = np.linspace(pr.real_yield_pct.min() - .2, pr.real_yield_pct.max() + .2, 20)
            f.add_trace(go.Scatter(x=xs, y=a + b * xs, mode="lines", hoverinfo="skip", showlegend=False,
                line=dict(color=dz.INK, width=1.4, dash=dz.DASH)))
            for idx, txt in [(0, pr.date.iloc[0].strftime("%b %Y")), (-1, pr.date.iloc[-1].strftime("%b %Y"))]:
                endlabel(f, pr.real_yield_pct.iloc[idx], pr.price_usd_oz.iloc[idx], f"<b>{txt}</b>", dz.INK)
            endlabel(f, xs[-1], a + b * xs[-1], f"old rule ({fit[0]}–{fit[1]})")
            f.update_xaxes(title="US 10-year real yield, %", zeroline=True, zerolinecolor=dz.GHOST)
            f.update_yaxes(title="gold, $ / oz")
            f.update_layout(showlegend=True, legend=dict(orientation="h", y=1.08, x=0, font=dict(size=11)))
            chart(f, 430)
        with right:
            st.subheader("Is the link still there?")
            st.caption(f"Rolling {roll}-month correlation between monthly changes in the gold price and in "
                       "the real yield. Below zero: gold rises when real yields fall.")
            tag("price")
            ch = pr.set_index("date")[["price_usd_oz", "real_yield_pct"]].diff()
            ch["price_usd_oz"] = pr.set_index("date").price_usd_oz.pct_change()
            corr = ch.price_usd_oz.rolling(roll).corr(ch.real_yield_pct).dropna()
            f = go.Figure(go.Scatter(x=corr.index, y=corr.values, mode="lines",
                line=dict(color=dz.GOLD, width=2.4), fill="tozeroy", fillcolor="rgba(163,120,10,.10)",
                hovertemplate="%{x|%b %Y}: %{y:.2f}<extra></extra>"))
            f.add_hline(y=0, line=dict(color=dz.INK, width=1))
            events(f, label=False)
            if len(corr):
                endlabel(f, corr.index[-1], corr.iloc[-1], f"<b>{corr.iloc[-1]:+.2f}</b>", dz.GOLD)
            f.update_yaxes(range=[-1, 1], title="correlation", tickformat=".1f")
            chart(f, 430)

        st.subheader("Actual price against the old rule")
        st.caption("Solid: actual price. Dashed: the price the fit years' relationship gives for each month's "
                   "real yield. Shaded: the gap.")
        tag("price")
        f = go.Figure()
        f.add_trace(go.Scatter(x=pr.date, y=pr.implied, mode="lines", name="old rule",
            line=dict(color=dz.INK, width=1.3, dash=dz.DASH)))
        f.add_trace(go.Scatter(x=pr.date, y=pr.price_usd_oz, mode="lines", name="price",
            line=dict(color=dz.GOLD, width=2.6), fill="tonexty", fillcolor="rgba(163,120,10,.13)"))
        f.add_vrect(x0=f"{fit[0]}-01-01", x1=f"{fit[1]}-12-31", fillcolor=dz.GHOST, opacity=.25, line_width=0,
                    annotation_text="fit years", annotation_position="top left",
                    annotation_font=dict(size=11, color=dz.FAINT))
        events(f, label=True)
        endlabel(f, pr.date.iloc[-1], pr.price_usd_oz.iloc[-1], f"<b>{pr.price_usd_oz.iloc[-1]:,.0f}</b> $/oz", dz.GOLD)
        endlabel(f, pr.date.iloc[-1], pr.implied.iloc[-1], "old rule")
        f.update_layout(hovermode="x unified")
        chart(f, 330)

        st.subheader("The gap, month by month")
        unit = st.radio("Show the gap as", ["$ per ounce", "% of the old-rule price"], horizontal=True,
                        key="premium_unit")
        tag("price")
        col, title = ("premium", "$ / oz") if unit == "$ per ounce" else ("share", "% above the old rule")
        f = go.Figure(go.Bar(x=pr.date, y=pr[col],
            marker_color=[dz.GOLD if v >= 0 else dz.FAINT for v in pr[col]],
            hovertemplate="%{x|%b %Y}: %{y:,.0f}" + (" $/oz" if col == "premium" else "%") + "<extra></extra>"))
        events(f, label=False)
        endlabel(f, pr.date.iloc[-1], pr[col].iloc[-1],
                 f"<b>{pr[col].iloc[-1]:,.0f}</b>" + (" $/oz" if col == "premium" else "%"), dz.GOLD)
        f.update_yaxes(title=title, tickformat=",.0f")
        chart(f, 240)

# ============================================================== DECLARED =====
with tabD:
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.subheader("Western investor holdings")
        st.caption(f"Is the yield-sensitive holder buying this move or "
                   f"selling into it? — as of {fmt(asof['etf'])}")
        tag("etf")
        f = go.Figure(go.Scatter(x=etf.date, y=etf.tonnes, mode="lines",
            line=dict(color=dz.hue("West"), width=2.4)))
        events(f, label=False)
        endlabel(f, etf.date.iloc[-1], e_now, f"<b>{e_now:,.0f}</b> t",
                 dz.hue("West"))
        chart(f, 330)
    with right:
        st.subheader("Declared official sector")
        window = st.select_slider("Compare over the last", options=[3, 6, 12, 24], value=12,
                                  format_func=lambda m: f"{m} months", key="window")
        measure = st.radio("Measure", ["Tonnes", "Share of net buying"], horizontal=True, key="measure")
        st.caption(f"Trailing {window}-month reported change — IMF, {fmt(asof['declared'])}")
        tag("declared")
        tw = (declared[declared.date > asof["declared"] - pd.DateOffset(months=window)]
              .groupby("country").net_purchases_t.sum())
        if measure == "Tonnes":
            s = tw.sort_values()
            labels, xtitle = [f"{v:+,.0f}" for v in s.values], "tonnes"
        else:   # each bank's share of all net buying (sellers shown as negative shares)
            s = (tw / tw[tw > 0].sum() * 100).sort_values()
            labels, xtitle = [f"{v:+.0f}%" for v in s.values], "% of all net buying"
        f = go.Figure(go.Bar(x=s.values, y=s.index, orientation="h",
            marker_color=[dz.hue(c) for c in s.index],
            text=labels, textposition="outside",
            textfont=dict(size=11, color=dz.FAINT), cliponaxis=False))
        f.update_xaxes(title=xtitle, showgrid=False)
        f.update_yaxes(side="left", gridcolor=dz.PAPER)
        chart(f, 330)

    with st.expander(f"{window}-month detail per bank"):
        st.markdown('<span class="tag sample">Sample data · synthetic, for illustration only</span>'
                    if is_sample("declared") else "", unsafe_allow_html=True)
        ranked = tw.sort_values(ascending=False).index.tolist()
        picked = st.multiselect("Banks to compare", ranked, default=ranked[:5], key="banks")
        d12 = declared[(declared.date > asof["declared"] - pd.DateOffset(months=window))
                       & declared.country.isin(picked)].copy()
        order = [c for c in ranked if c in picked]
        if not order:
            st.info("Pick at least one bank.")
        else:
            fig = px.bar(d12, x="date", y="net_purchases_t", facet_col="country",
                         facet_col_wrap=min(5, len(order)), category_orders={"country": order},
                         color="country",
                         color_discrete_map={c: dz.hue(c) for c in order},
                         facet_row_spacing=.10, facet_col_spacing=.03)
            fig.update_yaxes(matches=None, title=None, side="left")
            fig.update_xaxes(title=None, showticklabels=False)
            fig.for_each_annotation(lambda a:
                a.update(text=a.text.split("=")[-1], font=dict(size=12)))
            chart(fig, 230 * ((len(order) + 4) // 5) + 60)

# ============================================================== INFERRED =====
with tabI:
    st.subheader("The gap")
    st.caption(f"How much official buying goes unreported each quarter? — "
               f"{gap.quarter_end.iloc[-1].to_period('Q')}")
    tag("gap", "declared")
    f = go.Figure()
    f.add_trace(go.Scatter(x=gap.quarter_end, y=gap.imf_reported_t,
        mode="lines", line=dict(width=0), hoverinfo="skip"))
    f.add_trace(go.Scatter(x=gap.quarter_end, y=gap.wgc_estimate_t,
        name="WGC estimate", mode="lines",
        line=dict(color=dz.INK, width=1.6, dash=dz.DASH),
        fill="tonexty", fillcolor="rgba(163,120,10,.16)"))
    f.add_trace(go.Bar(x=gap.quarter_end, y=gap.imf_reported_t,
        name="reported to IMF", marker_color=dz.INK, opacity=.85))
    events(f, label=True)
    endlabel(f, gap.quarter_end.iloc[-1], gap.wgc_estimate_t.iloc[-1],
             f"WGC <b>{gap.wgc_estimate_t.iloc[-1]:,.0f}</b> t")
    endlabel(f, gap.quarter_end.iloc[-1], gap.imf_reported_t.iloc[-1],
             f"IMF <b>{gap.imf_reported_t.iloc[-1]:,.0f}</b> t")
    f.update_yaxes(title="tonnes / quarter")
    chart(f, 430)
    st.caption("Bars: purchases reported to the IMF. Dashed: World Gold "
               "Council estimate of actual official demand. Shaded: the "
               "unreported residual.")

    st.subheader("Physical flow west to east")
    st.caption(f"Where are the bars going, and is the float being "
               f"replenished? — Swiss customs, {fmt(asof['swiss'])}")
    tag("swiss")
    f = go.Figure()
    for dest in ["other", "UAE + Gulf", "UK + US", "Turkey", "India",
                 "China + HK"]:
        d = swiss[swiss.destination == dest]
        f.add_trace(go.Scatter(x=d.date, y=d.tonnes, name=dest,
            stackgroup="flow", mode="none", fillcolor=dz.hue(dest),
            hovertemplate=f"{dest}: %{{y:.0f}} t<extra></extra>"))
    events(f, label=False)
    show_repl = st.toggle("show mine replenishment")
    if show_repl:
        f.add_hline(y=dz.MINE_TOTAL_TPM,
            line=dict(color=dz.INK, width=1.2, dash="dash"),
            annotation_text="all mine supply ≈ 300 t/mo",
            annotation_position="top left")
        f.add_hline(y=dz.MINE_WESTERN_TPM,
            line=dict(color=dz.INK, width=1.2, dash="dot"),
            annotation_text="enters Western circuit ≈ 200 t/mo",
            annotation_position="bottom left")
    f.update_yaxes(title="tonnes / month", range=[0, 330])
    f.update_layout(showlegend=True, legend=dict(orientation="h", y=1.06,
        x=0, font=dict(size=12)), hovermode="x unified")
    chart(f, 400)
    if show_repl:
        st.caption("Output above the lower line drains the Western float "
                   "faster than the ground refills it. The space between the "
                   "lines is mine supply born outside the circuit (China, "
                   "Russia, Uzbekistan, Kazakhstan).")

st.caption("Real data in this build: COMEX gold front-month futures (GC=F, daily closes via Yahoo Finance, "
           "averaged by month) and the US 10-year TIPS real yield (FRED DFII10, monthly average), saved in "
           "data/raw/ on 13 Oct 2026; the yield-implied level is fitted on 2020–21 months. "
           "Sample data (synthetic): GLD + IAU holdings, IMF central-bank purchases, the WGC gap and Swiss "
           "exports; when live these come from the GLD and IAU bar lists, IMF International Financial "
           "Statistics, World Gold Council Gold Demand Trends and Swiss-Impex tariff heading 7108. "
           "Event rules: Feb 22 reserve freeze, Jun 22 G7 import ban, Jun 25 Iran war, Nov 25 CBR sales "
           "begin, May 26 escalation.")
