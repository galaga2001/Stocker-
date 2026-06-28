"""Stocker — Streamlit web interface.

Launch with:  streamlit run app.py
"""

from __future__ import annotations

import os
import time

import pandas as pd
import streamlit as st

from stocker.config_manager import load_config
from stocker.data_fetcher import BadTickerError, DataFetcher, normalize_crypto_ticker, SUPPORTED_CRYPTO
from stocker.positions_manager import add_or_update, delete, load_positions, save_positions
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

st.markdown("""
<style>
    div[data-testid="stMetricValue"] { font-size: 1.4rem; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Mode constants
# ---------------------------------------------------------------------------
MODE_STOCK  = "📈  Stocks"
MODE_CRYPTO = "₿  Crypto"

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
_DEFAULTS: dict = {
    "mode": MODE_STOCK,
    "monitoring": False,
    "fetcher": None,
    "scenarios": [],
    "last_snap": None,
    "metrics": None,
    "notified_ids": set(),
    "last_fetch_time": 0.0,
    "error": None,
    # stock defaults
    "stock_ticker": "",
    "stock_shares": 10,
    "stock_cost_basis": 100.00,
    "stock_profit_target": 200.00,
    "stock_scenario_step": 1,
    # crypto defaults
    "crypto_ticker": "",
    "crypto_shares": 0.5,
    "crypto_cost_basis": 50000.00,
    "crypto_profit_target": 500.00,
    "crypto_scenario_step": 0.1,
    # shared
    "poll_interval": 10,
    "notifications_on": True,
    # saved positions
    "saved_positions": [],
    "selected_position": "— New position —",
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# Load saved positions once per session
if "positions_loaded" not in st.session_state:
    st.session_state.saved_positions = load_positions()
    st.session_state.positions_loaded = True

# Load API keys from environment variables (set on the server — never shown to users)
# Streamlit Cloud: set these in App Settings → Secrets
_ALPACA_KEY    = os.environ.get("ALPACA_API_KEY",    "")
_ALPACA_SECRET = os.environ.get("ALPACA_API_SECRET", "")



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def stop_monitoring() -> None:
    st.session_state.monitoring   = False
    st.session_state.fetcher      = None
    st.session_state.last_snap    = None
    st.session_state.metrics      = None
    st.session_state.scenarios    = []
    st.session_state.error        = None


def is_crypto() -> bool:
    return st.session_state.mode == MODE_CRYPTO


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 📈 Stocker")
    st.caption("Live Profit Monitor")
    st.divider()

    # --- Mode toggle ---
    new_mode = st.radio(
        "Asset type",
        [MODE_STOCK, MODE_CRYPTO],
        index=0 if st.session_state.mode == MODE_STOCK else 1,
        horizontal=True,
        disabled=st.session_state.monitoring,
    )
    if new_mode != st.session_state.mode:
        stop_monitoring()
        st.session_state.mode = new_mode
        st.rerun()

    st.divider()

    # --- Saved positions dropdown ---
    NEW_POSITION = "— New position —"
    position_names = [NEW_POSITION] + [p["name"] for p in st.session_state.saved_positions]
    current_selection = (
        st.session_state.selected_position
        if st.session_state.selected_position in position_names
        else NEW_POSITION
    )

    selected = st.selectbox(
        "Saved Positions",
        options=position_names,
        index=position_names.index(current_selection),
        disabled=st.session_state.monitoring,
    )

    # When user picks a different position, auto-fill all fields and rerun
    if selected != st.session_state.selected_position:
        st.session_state.selected_position = selected
        if selected != NEW_POSITION:
            pos = next(p for p in st.session_state.saved_positions if p["name"] == selected)
            mode_key = pos.get("mode", "stock")
            st.session_state.mode = MODE_STOCK if mode_key == "stock" else MODE_CRYPTO
            st.session_state[f"{mode_key}_ticker"]        = pos["ticker"]
            st.session_state[f"{mode_key}_shares"]        = pos["shares"]
            st.session_state[f"{mode_key}_cost_basis"]    = pos["cost_basis"]
            st.session_state[f"{mode_key}_profit_target"] = pos["profit_target"]
            st.session_state[f"{mode_key}_scenario_step"] = pos.get("scenario_step", 1)
        st.rerun()

    st.divider()
    locked = st.session_state.monitoring

    # --- Inputs change based on mode ---
    if not is_crypto():
        ticker = st.text_input(
            "Ticker Symbol",
            value=st.session_state.stock_ticker,
            placeholder="e.g. AAPL, TSLA, MSFT",
            disabled=locked,
        ).strip().upper()

        shares = float(st.number_input(
            "Shares Held",
            min_value=1, max_value=1_000_000,
            value=int(st.session_state.stock_shares),
            step=1,
            disabled=locked,
        ))

        cost_basis = st.number_input(
            "Average Cost Basis per Share ($)",
            min_value=0.01,
            value=float(st.session_state.stock_cost_basis),
            format="%.2f",
            disabled=locked,
        )

        profit_target = st.number_input(
            "Profit Target ($)",
            min_value=0.01,
            value=float(st.session_state.stock_profit_target),
            format="%.2f",
            disabled=locked,
        )

        scenario_step_options = [1, 2, 5, 10, 25, 50, 100]
        scenario_step = float(st.select_slider(
            "Scenario granularity (shares per row)",
            options=scenario_step_options,
            value=min(int(st.session_state.stock_scenario_step), max(scenario_step_options)),
            disabled=locked,
            help="Lower = more rows in the scenario table",
        ))

    else:  # Crypto mode
        raw_ticker = st.text_input(
            "Coin Symbol",
            value=st.session_state.crypto_ticker or "",
            placeholder="e.g. BTC, ETH, SOL",
            disabled=locked,
            help="Type the coin symbol — USD is added automatically",
        ).strip().upper()
        ticker = normalize_crypto_ticker(raw_ticker) if raw_ticker else ""
        st.caption("Supported: " + ", ".join(SUPPORTED_CRYPTO))

        shares = st.number_input(
            "Amount Held (coins)",
            min_value=0.000001,
            max_value=1_000_000.0,
            value=float(st.session_state.crypto_shares),
            format="%.6f",
            step=0.001,
            disabled=locked,
        )

        cost_basis = st.number_input(
            "Average Cost Basis per Coin ($)",
            min_value=0.000001,
            value=float(st.session_state.crypto_cost_basis),
            format="%.2f",
            disabled=locked,
        )

        profit_target = st.number_input(
            "Profit Target ($)",
            min_value=0.01,
            value=float(st.session_state.crypto_profit_target),
            format="%.2f",
            disabled=locked,
        )

        crypto_step_options = [0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5]
        scenario_step = st.select_slider(
            "Scenario granularity (coins per row)",
            options=crypto_step_options,
            value=st.session_state.crypto_scenario_step,
            disabled=locked,
            help="Lower = more rows in the scenario table",
        )

    st.divider()
    poll_interval = st.slider(
        "Price refresh (seconds)",
        min_value=5, max_value=120,
        value=st.session_state.poll_interval,
        disabled=locked,
    )
    notifications_on = st.toggle(
        "Notifications",
        value=st.session_state.notifications_on,
    )
    st.session_state.notifications_on = notifications_on

    st.divider()

    # --- Save / Delete ---
    if not locked:
        unit = "coins" if is_crypto() else "shares"
        default_name = f"{ticker} — {shares} {unit} @ ${cost_basis:,.2f}" if ticker else ""
        save_name = st.text_input(
            "Save as",
            value=st.session_state.selected_position
                  if st.session_state.selected_position != "— New position —"
                  else default_name,
            placeholder="Give this position a name",
        )
        save_col, del_col = st.columns(2)
        if save_col.button("💾 Save", use_container_width=True, disabled=not save_name):
            new_pos = {
                "name": save_name,
                "mode": "crypto" if is_crypto() else "stock",
                "ticker": ticker,
                "shares": shares,
                "cost_basis": cost_basis,
                "profit_target": profit_target,
                "scenario_step": scenario_step,
            }
            updated = add_or_update(st.session_state.saved_positions, new_pos)
            save_positions(updated)
            st.session_state.saved_positions = updated
            st.session_state.selected_position = save_name
            st.toast(f'Saved "{save_name}"', icon="💾")
            st.rerun()

        can_delete = st.session_state.selected_position != "— New position —"
        if del_col.button("🗑 Delete", use_container_width=True, disabled=not can_delete):
            updated = delete(st.session_state.saved_positions, st.session_state.selected_position)
            save_positions(updated)
            st.session_state.saved_positions = updated
            st.session_state.selected_position = "— New position —"
            st.rerun()

    st.divider()

    # --- Start / Stop ---
    if not locked:
        start_clicked = st.button(
            "▶  Start Monitoring",
            type="primary",
            use_container_width=True,
            disabled=not ticker,
        )
        if start_clicked:
            st.session_state.error = None
            if not is_crypto() and not (_ALPACA_KEY and _ALPACA_SECRET):
                st.session_state.error = "Stock data is unavailable right now. Try crypto mode instead."
                st.rerun()
            base = ticker.split("-")[0].split("/")[0]
            if is_crypto() and base not in SUPPORTED_CRYPTO:
                st.session_state.error = (
                    f"'{base}' is not supported. Supported coins: {', '.join(SUPPORTED_CRYPTO)}"
                )
                st.rerun()
            mode_key = "crypto" if is_crypto() else "stock"
            with st.spinner(f"Connecting to {ticker}…"):
                try:
                    fetcher = DataFetcher(
                        ticker,
                        mode="crypto" if is_crypto() else "stock",
                        api_key=_ALPACA_KEY,
                        api_secret=_ALPACA_SECRET,
                    )
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
                            "Check that your profit target is achievable with your position."
                        )
                    else:
                        # Persist mode-specific inputs
                        st.session_state[f"{mode_key}_ticker"]        = ticker
                        st.session_state[f"{mode_key}_shares"]        = shares
                        st.session_state[f"{mode_key}_cost_basis"]    = cost_basis
                        st.session_state[f"{mode_key}_profit_target"] = profit_target
                        st.session_state[f"{mode_key}_scenario_step"] = scenario_step
                        st.session_state.poll_interval = poll_interval
                        st.session_state.update(
                            fetcher=fetcher,
                            scenarios=scenarios,
                            notified_ids=set(),
                            last_fetch_time=0.0,
                            last_snap=None,
                            metrics=None,
                            monitoring=True,
                            # stash current position for display
                            _active_shares=shares,
                            _active_cost_basis=cost_basis,
                            _active_profit_target=profit_target,
                        )
                        st.rerun()
                except BadTickerError as exc:
                    st.session_state.error = str(exc)
    else:
        if st.button("⏹  Stop Monitoring", use_container_width=True):
            stop_monitoring()
            st.rerun()

    if st.session_state.error:
        st.error(st.session_state.error)


# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------
if not st.session_state.monitoring:
    icon  = "₿" if is_crypto() else "📈"
    label = "Crypto" if is_crypto() else "Stocks"
    st.markdown(f"# {icon} Stocker — {label}")
    st.markdown(
        "Fill in your position in the **sidebar** and click "
        "**▶ Start Monitoring** to begin."
    )
    st.divider()
    col1, col2, col3 = st.columns(3)
    unit = "coins" if is_crypto() else "shares"
    col1.info(f"**Step 1**\nEnter the ticker symbol, how many {unit} you hold, and what you paid per {unit[:-1]}.")
    col2.info("**Step 2**\nSet the exact dollar profit you want to net from a sell.")
    col3.info("**Step 3**\nHit Start — every way to hit your target is shown, and you get an alert the moment a price is reached.")

else:
    # -----------------------------------------------------------------------
    # Fetch price when interval has elapsed
    # -----------------------------------------------------------------------
    elapsed = time.time() - st.session_state.last_fetch_time
    needs_fetch = elapsed >= st.session_state.poll_interval or st.session_state.last_snap is None

    if needs_fetch:
        try:
            snap = st.session_state.fetcher.fetch()
            metrics = compute_metrics(
                st.session_state._active_cost_basis,
                snap.price,
                st.session_state._active_shares,
            )
            st.session_state.last_snap       = snap
            st.session_state.metrics         = metrics
            st.session_state.last_fetch_time = time.time()

            ts = snap.timestamp.strftime("%H:%M:%S")
            update_trigger_status(st.session_state.scenarios, snap.price, ts)

            for s in st.session_state.scenarios:
                sid = id(s)
                if s.triggered and sid not in st.session_state.notified_ids:
                    st.session_state.notified_ids.add(sid)
                    if st.session_state.notifications_on:
                        unit = "coins" if is_crypto() else "shares"
                        amt  = f"{s.shares_to_sell:.4f}" if is_crypto() else f"{s.shares_to_sell:.0f}"
                        st.toast(
                            f"Target hit! Sell {amt} {unit} @ ${s.required_price:,.2f}",
                            icon="🔔",
                        )
        except Exception as exc:
            st.warning(f"Price fetch error — will retry: {exc}")

    snap    = st.session_state.last_snap
    metrics = st.session_state.metrics

    if snap is None or metrics is None:
        st.info("Fetching first price…")
    else:
        remaining = max(0, st.session_state.poll_interval - (time.time() - st.session_state.last_fetch_time))

        # --- Header ---
        if is_crypto():
            mkt_badge = "🟣 24 / 7"
        else:
            mkt_badge = "🟢 Market Open" if snap.is_market_open else "🔴 Market Closed"

        head_l, head_r = st.columns([3, 1])
        with head_l:
            st.markdown(f"## {snap.ticker} &nbsp;&nbsp; {mkt_badge}")
        with head_r:
            st.caption(f"Last update: {snap.timestamp.strftime('%H:%M:%S %Z')}")
            st.caption(f"Next refresh in **{int(remaining)}s**")

        # --- Metric cards ---
        price_fmt = f"${snap.price:,.2f}" if snap.price >= 1 else f"${snap.price:.6f}"
        pnl_color = "normal" if metrics.unrealized_pnl >= 0 else "inverse"
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Current Price",  price_fmt)
        c2.metric("Cost Basis",     f"${metrics.cost_basis:,.2f}")
        c3.metric(
            "Unrealized P&L",
            f"${metrics.unrealized_pnl:+,.2f}",
            delta=f"{metrics.unrealized_pnl_pct:+.2f}%",
            delta_color=pnl_color,
        )
        c4.metric("Profit Target",  f"${st.session_state._active_profit_target:,.2f}")

        st.divider()

        # --- Triggered alerts ---
        triggered = [s for s in st.session_state.scenarios if s.triggered]
        if triggered:
            st.markdown("### 🔔 Active Alerts")
            unit = "coins" if is_crypto() else "share(s)"
            for s in triggered:
                amt = f"{s.shares_to_sell:.4f}" if is_crypto() else f"{s.shares_to_sell:.0f}"
                st.success(
                    f"**Sell {amt} {unit} @ ${s.required_price:,.2f}** — "
                    f"price target crossed at **{s.trigger_time}** — "
                    f"nets you **${s.profit_target:,.2f}**"
                )
            st.divider()

        # --- Scenario table ---
        unit_label = "Coins to Sell" if is_crypto() else "Shares to Sell"
        st.markdown("### Sell Scenarios")
        st.caption(
            "Each row shows the exact price you need to sell at to net your profit target "
            f"for a given number of {('coins' if is_crypto() else 'shares')}."
        )

        rows = []
        for s in st.session_state.scenarios:
            gap = snap.price - s.required_price
            # "Almost there" threshold: within 0.2% of required price (works for both BTC and penny stocks)
            close_threshold = s.required_price * 0.002
            if s.triggered:
                status = "✅  TRIGGERED"
            elif gap >= -close_threshold:
                status = "🟡  Almost there"
            else:
                status = "⏳  Waiting"

            amt = f"{s.shares_to_sell:.4f}" if is_crypto() else f"{s.shares_to_sell:.0f}"
            rows.append({
                unit_label: amt,
                "Sell at This Price": s.required_price,
                "Current Price": snap.price,
                "Gap to Target": gap,
                "Status": status,
                "Triggered At": s.trigger_time or "—",
            })

        df = pd.DataFrame(rows)
        price_fmt_str = "$%.4f" if snap.price < 1 else "$%.2f"

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                unit_label: st.column_config.TextColumn(unit_label, width="medium"),
                "Sell at This Price": st.column_config.NumberColumn(
                    "Sell at This Price", format=price_fmt_str, width="medium"
                ),
                "Current Price": st.column_config.NumberColumn(
                    "Current Price", format=price_fmt_str, width="medium"
                ),
                "Gap to Target": st.column_config.NumberColumn(
                    "Gap to Target", format="$%+.2f", width="medium"
                ),
                "Status": st.column_config.TextColumn("Status", width="medium"),
                "Triggered At": st.column_config.TextColumn("Triggered At", width="small"),
            },
        )

        st.caption(
            "💡 Tip: a positive Gap means the current price already exceeds that row's sell target. "
            "✅ means an alert has fired for that row."
        )

    # -----------------------------------------------------------------------
    # Auto-refresh every second
    # -----------------------------------------------------------------------
    time.sleep(1)
    st.rerun()
