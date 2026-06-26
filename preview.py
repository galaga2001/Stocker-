"""Render a static dashboard preview with mock data and export to SVG."""

from datetime import datetime
from zoneinfo import ZoneInfo

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel

from stocker.dashboard import build_header_panel, build_scenario_table, build_footer
from stocker.data_fetcher import PriceSnapshot
from stocker.profit_calculator import compute_metrics
from stocker.scenario_generator import Scenario

# --- Mock position ---
TICKER = "AAPL"
SHARES = 50
COST_BASIS = 145.00
PROFIT_TARGET = 500.00
CURRENT_PRICE = 156.72

snap = PriceSnapshot(
    ticker=TICKER,
    price=CURRENT_PRICE,
    timestamp=datetime.now(ZoneInfo("America/New_York")),
    is_market_open=True,
)

metrics = compute_metrics(COST_BASIS, CURRENT_PRICE, SHARES)

# Manually build the scenario list so we control which ones are triggered
scenarios = [
    Scenario(50, 155.00, PROFIT_TARGET, COST_BASIS, triggered=True,  trigger_time="14:03:22"),
    Scenario(40, 157.50, PROFIT_TARGET, COST_BASIS, triggered=False, trigger_time=""),
    Scenario(30, 161.67, PROFIT_TARGET, COST_BASIS, triggered=False, trigger_time=""),
    Scenario(25, 165.00, PROFIT_TARGET, COST_BASIS, triggered=False, trigger_time=""),
    Scenario(20, 170.00, PROFIT_TARGET, COST_BASIS, triggered=False, trigger_time=""),
    Scenario(15, 178.33, PROFIT_TARGET, COST_BASIS, triggered=False, trigger_time=""),
    Scenario(10, 195.00, PROFIT_TARGET, COST_BASIS, triggered=False, trigger_time=""),
    Scenario(5,  245.00, PROFIT_TARGET, COST_BASIS, triggered=False, trigger_time=""),
]

console = Console(record=True, width=100)

with console:
    header = build_header_panel(snap, metrics, PROFIT_TARGET)
    table  = build_scenario_table(scenarios, CURRENT_PRICE)
    footer = build_footer(poll_interval=10, next_poll=7)
    console.print(header)
    console.print(table)
    console.print(footer)

svg = console.export_svg(title="Stocker — Live Profit Monitor")
with open("/tmp/stocker_preview.svg", "w") as f:
    f.write(svg)

print("Preview written to /tmp/stocker_preview.svg")
