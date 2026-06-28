#!/usr/bin/env python3
"""Stocker — main entry point.

Usage examples:
  python main.py                                # interactive prompts
  python main.py --ticker AAPL --shares 10 --cost-basis 145.00 --target 200
  python main.py --config ~/.stocker/config.yaml
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.prompt import FloatPrompt, IntPrompt, Prompt

from stocker.config_manager import AppConfig, PositionConfig, load_config, save_config
from stocker.dashboard import Dashboard
from stocker.data_fetcher import BadTickerError, DataFetcher
from stocker.notifier import Notifier
from stocker.profit_calculator import compute_metrics
from stocker.scenario_generator import generate_scenarios, update_trigger_status

console = Console()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stocker",
        description="Monitor live stock prices toward a profit target.",
    )
    p.add_argument("--ticker", "-t", help="Stock ticker symbol (e.g. AAPL)")
    p.add_argument("--shares", "-s", type=float, help="Number of shares held")
    p.add_argument("--cost-basis", "-c", type=float, dest="cost_basis",
                   help="Average price paid per share")
    p.add_argument("--target", "-g", type=float, dest="profit_target",
                   help="Profit target in dollars")
    p.add_argument("--config", type=Path, help="Path to YAML config file")
    p.add_argument("--save-config", action="store_true",
                   help="Persist entered values to config file")
    p.add_argument("--interval", type=int, default=None,
                   help="Poll interval in seconds (default: 10)")
    p.add_argument("--notify", choices=["desktop", "email", "sms", "none"],
                   help="Notification method")
    p.add_argument("--step", type=int, default=None,
                   help="Share increment between scenarios (default: 1)")
    p.add_argument("--extended-hours", action="store_true",
                   help="Suppress market-closed warnings during extended hours")
    return p


# ---------------------------------------------------------------------------
# Interactive prompts
# ---------------------------------------------------------------------------

def prompt_for_position(cfg: AppConfig, args: argparse.Namespace) -> PositionConfig:
    pos = cfg.position

    ticker = args.ticker or (pos.ticker if pos.ticker else None)
    if not ticker:
        ticker = Prompt.ask("[cyan]Ticker symbol[/cyan]").upper()

    shares = args.shares or (pos.shares if pos.shares else None)
    if not shares:
        shares = FloatPrompt.ask("[cyan]Number of shares held[/cyan]")

    cost_basis = args.cost_basis or (pos.cost_basis if pos.cost_basis else None)
    if not cost_basis:
        cost_basis = FloatPrompt.ask("[cyan]Average cost basis per share ($)[/cyan]")

    profit_target = args.profit_target or (pos.profit_target if pos.profit_target else None)
    if not profit_target:
        profit_target = FloatPrompt.ask("[cyan]Profit target ($)[/cyan]")

    return PositionConfig(
        ticker=ticker,
        shares=shares,
        cost_basis=cost_basis,
        profit_target=profit_target,
    )


# ---------------------------------------------------------------------------
# Main monitor loop
# ---------------------------------------------------------------------------

def run_monitor(cfg: AppConfig) -> None:
    pos = cfg.position
    poll_interval = cfg.poll_interval
    notify = Notifier(cfg.notification)

    console.print(f"\n[bold cyan]Validating ticker [white]{pos.ticker}[/white]…[/bold cyan]")
    try:
        fetcher = DataFetcher(pos.ticker)
    except BadTickerError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        sys.exit(1)

    scenarios = generate_scenarios(
        total_shares=pos.shares,
        cost_basis=pos.cost_basis,
        profit_target=pos.profit_target,
        step=cfg.scenario_step,
    )

    if not scenarios:
        console.print(
            "[bold red]No valid scenarios generated.[/bold red] "
            "Check that your profit target is achievable with your share count and cost basis."
        )
        sys.exit(1)

    console.print(
        f"[green]✓[/green] {len(scenarios)} scenario(s) generated. "
        f"Cheapest target: ${scenarios[0].required_price:.4f} (sell {scenarios[0].shares_to_sell} share(s))\n"
    )

    notified_ids: set[int] = set()

    with Dashboard(poll_interval) as dash:
        while True:
            try:
                snap = fetcher.fetch()
            except Exception as exc:
                console.log(f"[yellow]Price fetch error: {exc}[/yellow]")
                time.sleep(poll_interval)
                continue

            metrics = compute_metrics(pos.cost_basis, snap.price, pos.shares)
            ts = snap.timestamp.strftime("%H:%M:%S")
            update_trigger_status(scenarios, snap.price, ts)

            # Fire notifications for newly triggered scenarios
            for s in scenarios:
                sid = id(s)
                if s.triggered and sid not in notified_ids:
                    notified_ids.add(sid)
                    notify.alert(s, snap.price)

            # Countdown until next poll
            for remaining in range(poll_interval, 0, -1):
                dash.refresh(snap, metrics, scenarios, pos.profit_target, remaining)
                time.sleep(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    cfg = load_config(args.config)

    # Override config with CLI flags
    if args.interval is not None:
        cfg.poll_interval = args.interval
    if args.step is not None:
        cfg.scenario_step = args.step
    if args.notify:
        cfg.notification.method = args.notify

    cfg.position = prompt_for_position(cfg, args)

    if args.save_config:
        save_config(cfg)
        console.print("[green]Config saved.[/green]")

    # Basic sanity checks before starting
    pos = cfg.position
    if pos.shares <= 0:
        console.print("[red]Shares must be a positive number.[/red]")
        sys.exit(1)
    if pos.cost_basis <= 0:
        console.print("[red]Cost basis must be a positive number.[/red]")
        sys.exit(1)
    if pos.profit_target <= 0:
        console.print("[red]Profit target must be a positive number.[/red]")
        sys.exit(1)

    try:
        run_monitor(cfg)
    except KeyboardInterrupt:
        console.print("\n[bold cyan]Monitor stopped.[/bold cyan]")


if __name__ == "__main__":
    main()
