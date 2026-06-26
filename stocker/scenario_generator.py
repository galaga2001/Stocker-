"""Scenario generator — enumerate all valid (shares, sell_price) pairs that hit the profit target."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List

from stocker.profit_calculator import required_price_for_target


@dataclass
class Scenario:
    shares_to_sell: int
    required_price: float           # sell price needed to hit target
    profit_target: float
    cost_basis: float
    triggered: bool = False         # True once live price >= required_price
    trigger_time: str = ""


def generate_scenarios(
    total_shares: float,
    cost_basis: float,
    profit_target: float,
    step: int = 1,
    max_scenarios: int = 50,
) -> List[Scenario]:
    """Return one scenario per possible share count from *step* to *total_shares*.

    Each scenario shows the exact sell price that yields *profit_target*.
    Scenarios where the required price is at or below cost_basis are excluded
    (would require selling below cost to hit the target, which is impossible).
    """
    max_shares = int(math.floor(total_shares))
    scenarios: List[Scenario] = []

    for n in range(step, max_shares + 1, step):
        try:
            price = required_price_for_target(cost_basis, n, profit_target)
        except ValueError:
            continue
        if price <= cost_basis:
            # Can't profit below cost basis
            continue
        scenarios.append(
            Scenario(
                shares_to_sell=n,
                required_price=round(price, 4),
                profit_target=profit_target,
                cost_basis=cost_basis,
            )
        )
        if len(scenarios) >= max_scenarios:
            break

    # Sort ascending by required_price so cheapest target appears first
    scenarios.sort(key=lambda s: s.required_price)
    return scenarios


def update_trigger_status(scenarios: List[Scenario], current_price: float, timestamp: str) -> None:
    """Mark any un-triggered scenario as triggered if current price has reached it."""
    for s in scenarios:
        if not s.triggered and current_price >= s.required_price:
            s.triggered = True
            s.trigger_time = timestamp
