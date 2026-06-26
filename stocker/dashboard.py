"""Dashboard — Rich-based live CLI display that refreshes in place."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from stocker.data_fetcher import PriceSnapshot
from stocker.profit_calculator import ProfitMetrics
from stocker.scenario_generator import Scenario


console = Console()


def _price_color(current: float, target: float) -> str:
    if current >= target:
        return "bold green"
    ratio = current / target
    if ratio >= 0.98:
        return "yellow"
    return "white"


def _pnl_color(value: float) -> str:
    if value > 0:
        return "green"
    if value < 0:
        return "red"
    return "white"


def build_header_panel(
    snap: PriceSnapshot,
    metrics: ProfitMetrics,
    profit_target: float,
) -> Panel:
    mkt_status = "[green]OPEN[/green]" if snap.is_market_open else "[red]CLOSED[/red]"
    pnl_style = _pnl_color(metrics.unrealized_pnl)
    pct_style = _pnl_color(metrics.unrealized_pnl_pct)

    lines = [
        f"[bold cyan]{snap.ticker}[/bold cyan]    Market: {mkt_status}    "
        f"Updated: {snap.timestamp.strftime('%H:%M:%S %Z')}",
        "",
        f"  Current Price : [bold white]${snap.price:>10.4f}[/bold white]",
        f"  Cost Basis    : [white]${metrics.cost_basis:>10.4f}[/white]",
        f"  Shares Held   : [white]{metrics.shares_held:>10.0f}[/white]",
        f"  Unrealized P&L: [{pnl_style}]${metrics.unrealized_pnl:>+10.2f}  "
        f"({metrics.unrealized_pnl_pct:+.2f}%)[/{pnl_style}]",
        f"  Profit Target : [bold yellow]${profit_target:>10.2f}[/bold yellow]",
    ]
    return Panel("\n".join(lines), title="[bold]Stocker — Live Profit Monitor[/bold]", border_style="cyan")


def build_scenario_table(scenarios: List[Scenario], current_price: float) -> Table:
    table = Table(
        title="Sell Scenarios",
        box=box.SIMPLE_HEAVY,
        show_lines=True,
        expand=True,
    )
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Shares to Sell", justify="right", width=16)
    table.add_column("Required Price", justify="right", width=16)
    table.add_column("Current Price", justify="right", width=14)
    table.add_column("Gap to Target", justify="right", width=14)
    table.add_column("Status", justify="center", width=14)
    table.add_column("Triggered At", width=20)

    for i, s in enumerate(scenarios, 1):
        gap = current_price - s.required_price
        gap_str = f"${gap:+.4f}"

        if s.triggered:
            status = Text("● TRIGGERED", style="bold green")
            price_style = "bold green"
            gap_style = "green"
        elif gap >= -0.10:
            status = Text("◎ CLOSE", style="bold yellow")
            price_style = "yellow"
            gap_style = "yellow"
        else:
            status = Text("○ waiting", style="dim white")
            price_style = _price_color(current_price, s.required_price)
            gap_style = "dim"

        table.add_row(
            str(i),
            str(s.shares_to_sell),
            f"[{price_style}]${s.required_price:.4f}[/{price_style}]",
            f"${current_price:.4f}",
            f"[{gap_style}]{gap_str}[/{gap_style}]",
            status,
            s.trigger_time or "—",
        )

    return table


def build_footer(poll_interval: int, next_poll: int) -> Text:
    return Text(
        f"  Refreshing every {poll_interval}s  |  Next poll in {next_poll}s  |  Press Ctrl+C to exit",
        style="dim",
        justify="center",
    )


class Dashboard:
    """Context-manager wrapper around Rich Live."""

    def __init__(self, poll_interval: int):
        self._poll_interval = poll_interval
        self._live: Optional[Live] = None

    def __enter__(self) -> "Dashboard":
        self._live = Live(console=console, refresh_per_second=4, screen=False)
        self._live.__enter__()
        return self

    def __exit__(self, *args) -> None:
        if self._live:
            self._live.__exit__(*args)

    def refresh(
        self,
        snap: PriceSnapshot,
        metrics: ProfitMetrics,
        scenarios: List[Scenario],
        profit_target: float,
        next_poll: int,
    ) -> None:
        assert self._live is not None
        header = build_header_panel(snap, metrics, profit_target)
        table = build_scenario_table(scenarios, snap.price)
        footer = build_footer(self._poll_interval, next_poll)

        layout = Layout()
        layout.split_column(
            Layout(header, name="header", size=9),
            Layout(table, name="table"),
            Layout(footer, name="footer", size=1),
        )
        self._live.update(layout)
