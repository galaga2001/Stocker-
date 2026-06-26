"""Stocker — Streamlit web interface.

Launch with:  streamlit run app.py
"""

from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from stocker.config_manager import load_config
from stocker.data_fetcher import BadTickerError, DataFetcher
from stocker.profit_calculator import compute_metrics
from stocker.scenario_generator import generate_scenarios, update_trigger_status

# ---------------------------------------------------------------------------
# Page config — must be first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Stocker",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    .status-triggered { color: #00c853; font-weight: 700; }
    .status-close     { color: #ffd600; font-weight: 600; }
    .status-waiting   { color: #9e9e9e; }
    .gap-positive     { color: #00c853; }
    .gap-negative     { color: #ef5350; }
    .big-price        { font-size: 2.4rem; font-weight: 700; }
    div[data-testid="stMetricValue"] { font-size: 1.4rem; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
_DEFAULTS: dict = {
    "monitoring": False,
    "fetcher": None,
    "scenarios": [],
    "last_snap": None,
    "metrics": None,
    "notified_ids": set(),
    "last_fetch_time": 0.0,
    "error": None,
    # remembered inputs
    "ticker": "",
    "shares": 10,
    "cost_basis": 100.00,
    "profit_target": 200.00,
    "poll_interval": 10,
    "scenario_step": 1,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# Pre-fill from config file if one exists
_cfg = load_config()
if _cfg.position.ticker and not st.session_state.ticker:
    st.session_state.ticker      = _cfg.position.ticker
    st.session_state.shares      = int(_cfg.position.shares)
    st.session_state.cost_basis  = _cfg.position.cost_basis
    st.session_state.profit_target = _cfg.position.profit_target
    st.session_state.poll_interval = _cfg.poll_interval


# ---------------------------------------------------------------------------
# Sidebar — position inputs
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 📈 Stocker")
    st.caption("Live Stock Profit Monitor")
    st.divider()

    locked = st.session_state.monitoring  # disable inputs while running

    ticker = st.text_input(
        "Ticker Symbol",
        value=st.session_state.ticker,
        placeholder="e.g. AAPL",
        disabled=locked,
    ).strip().upper()

    shares = st.number_input(
        "Shares Held",
        min_value=1, max_value=100_000,
        value=int(st.session_state.shares),
        disabled=locked,
    )

    cost_basis = st.number_input(
        "Average Cost Basis per Share ($)",
        min_value=0.01,
        value=float(st.session_state.cost_basis),
        format="%.2f",
        disabled=locked,
    )

    profit_target = st.number_input(
        "Profit Target ($)",
        min_value=0.01,
        value=float(st.session_state.profit_target),
        format="%.2f",
        disabled=locked,
    )

    st.divider()
    st.caption("Settings")

    poll_interval = st.slider(
        "Price refresh (seconds)",
        min_value=5, max_value=120,
        value=st.session_state.poll_interval,
        disabled=locked,
    )

    scenario_step = st.select_slider(
        "Scenario granularity (shares per row)",
        options=[1, 2, 5, 10, 25, 50],
        value=st.session_state.scenario_step,
        disabled=locked,
        help="Lower = more rows in the scenario table",
    )

    st.divider()

    if not st.session_state.monitoring:
        start_clicked = st.button(
            "▶  Start Monitoring",
            type="primary",
            use_container_width=True,
            disabled=not ticker,
        )
        if start_clicked:
            st.session_state.error = None
            with st.spinner(f"Connecting to {ticker}…"):
                try:
                    fetcher = DataFetcher(ticker)
                    scenarios = generate_scenarios(
                        total_shares=shares,
                        cost_basis=cost_basis,
                        profit_target=profit_target,
                        step=scenario_step,
                        max_scenarios=30,
                    )
                    if not scenarios:
                        st.session_state.error = (
                            "No valid scenarios found. "
                            "Make sure your profit target is achievable with your share count."
                        )
                    else:
                        # Persist inputs to session state
                        st.session_state.update(
                            ticker=ticker,
                            shares=shares,
                            cost_basis=cost_basis,
                            profit_target=profit_target,
                            poll_interval=poll_interval,
                            scenario_step=scenario_step,
                            fetcher=fetcher,
                            scenarios=scenarios,
                            notified_ids=set(),
                            last_fetch_time=0.0,
                            last_snap=None,
                            metrics=None,
                            monitoring=True,
                        )
                        st.rerun()
                except BadTickerError as exc:
                    st.session_state.error = str(exc)
    else:
        if st.button("⏹  Stop Monitoring", use_container_width=True):
            st.session_state.monitoring = False
            st.session_state.fetcher = None
            st.rerun()

    if st.session_state.error:
        st.error(st.session_state.error)


# ---------------------------------------------------------------------------
# Main area — welcome screen or live dashboard
# ---------------------------------------------------------------------------
if not st.session_state.monitoring:
    st.markdown("# 📈 Stocker")
    st.markdown(
        "Enter your position details in the **sidebar** and click "
        "**▶ Start Monitoring** to begin."
    )
    st.divider()
    col1, col2, col3 = st.columns(3)
    col1.info("**Step 1**\nEnter your ticker symbol, number of shares, and what you paid per share.")
    col2.info("**Step 2**\nSet the exact dollar profit you want to net from a sell.")
    col3.info("**Step 3**\nHit Start — the dashboard shows every way to hit your target and alerts you when the price is reached.")

else:
    # -----------------------------------------------------------------------
    # Fetch price when interval has elapsed
    # -----------------------------------------------------------------------
    elapsed = time.time() - st.session_state.last_fetch_time
    if elapsed >= st.session_state.poll_interval or st.session_state.last_snap is None:
        try:
            snap = st.session_state.fetcher.fetch()
            metrics = compute_metrics(
                st.session_state.cost_basis,
                snap.price,
                st.session_state.shares,
            )
            st.session_state.last_snap = snap
            st.session_state.metrics = metrics
            st.session_state.last_fetch_time = time.time()

            ts = snap.timestamp.strftime("%H:%M:%S")
            update_trigger_status(st.session_state.scenarios, snap.price, ts)

            # In-app toast for newly triggered scenarios
            for s in st.session_state.scenarios:
                sid = id(s)
                if s.triggered and sid not in st.session_state.notified_ids:
                    st.session_state.notified_ids.add(sid)
                    st.toast(
                        f"Target hit! Sell {s.shares_to_sell} shares @ ${s.required_price:.2f}",
                        icon="🔔",
                    )
        except Exception as exc:
            st.warning(f"Price fetch error — will retry: {exc}")

    snap    = st.session_state.last_snap
    metrics = st.session_state.metrics

    # -----------------------------------------------------------------------
    # Render dashboard
    # -----------------------------------------------------------------------
    if snap is None or metrics is None:
        st.info("Fetching first price…")
    else:
        mkt_badge = "🟢 Market Open" if snap.is_market_open else "🔴 Market Closed"
        remaining = max(0, st.session_state.poll_interval - (time.time() - st.session_state.last_fetch_time))

        # Header row
        head_left, head_right = st.columns([3, 1])
        with head_left:
            st.markdown(f"## {snap.ticker} &nbsp;&nbsp; {mkt_badge}")
        with head_right:
            st.caption(f"Last update: {snap.timestamp.strftime('%H:%M:%S %Z')}")
            st.caption(f"Next refresh in **{int(remaining)}s**")

        # Key metrics
        pnl_color = "normal" if metrics.unrealized_pnl >= 0 else "inverse"
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Current Price",   f"${snap.price:,.2f}")
        c2.metric("Cost Basis",      f"${metrics.cost_basis:,.2f}")
        c3.metric(
            "Unrealized P&L",
            f"${metrics.unrealized_pnl:+,.2f}",
            delta=f"{metrics.unrealized_pnl_pct:+.2f}%",
            delta_color=pnl_color,
        )
        c4.metric("Profit Target",   f"${st.session_state.profit_target:,.2f}")

        st.divider()

        # -----------------------------------------------------------------------
        # Triggered alerts banner
        # -----------------------------------------------------------------------
        triggered = [s for s in st.session_state.scenarios if s.triggered]
        if triggered:
            st.markdown("### 🔔 Active Alerts")
            for s in triggered:
                st.success(
                    f"**Sell {s.shares_to_sell} share(s) @ ${s.required_price:.2f}** — "
                    f"price target crossed at **{s.trigger_time}** — "
                    f"nets you **${s.profit_target:,.2f}**"
                )
            st.divider()

        # -----------------------------------------------------------------------
        # Scenario table
        # -----------------------------------------------------------------------
        st.markdown("### Sell Scenarios")
        st.caption(
            "Each row shows the exact price you need to sell at to net your profit target "
            "for a given number of shares."
        )

        rows = []
        for s in st.session_state.scenarios:
            gap = snap.price - s.required_price
            if s.triggered:
                status = "✅  TRIGGERED"
            elif gap >= -0.10:
                status = "🟡  Almost there"
            else:
                status = "⏳  Waiting"

            rows.append({
                "Shares to Sell": s.shares_to_sell,
                "Sell at This Price": s.required_price,
                "Current Price": snap.price,
                "Gap to Target": gap,
                "Status": status,
                "Triggered At": s.trigger_time or "—",
            })

        df = pd.DataFrame(rows)

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Shares to Sell": st.column_config.NumberColumn(
                    "Shares to Sell", format="%d", width="medium"
                ),
                "Sell at This Price": st.column_config.NumberColumn(
                    "Sell at This Price", format="$%.2f", width="medium"
                ),
                "Current Price": st.column_config.NumberColumn(
                    "Current Price", format="$%.2f", width="medium"
                ),
                "Gap to Target": st.column_config.NumberColumn(
                    "Gap to Target", format="$%+.2f", width="medium"
                ),
                "Status": st.column_config.TextColumn("Status", width="medium"),
                "Triggered At": st.column_config.TextColumn("Triggered At", width="small"),
            },
        )

        st.caption(
            "💡 Tip: rows with a positive Gap are already above your sell target price. "
            "A green ✅ means a notification has fired for that row."
        )

    # -----------------------------------------------------------------------
    # Auto-refresh every second (only fetches API data on poll_interval)
    # -----------------------------------------------------------------------
    time.sleep(1)
    st.rerun()
