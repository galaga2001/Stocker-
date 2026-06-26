"""Profit calculator — core math for cost basis, P&L, and target pricing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProfitMetrics:
    cost_basis: float           # avg price paid per share
    current_price: float
    shares_held: float
    unrealized_pnl: float       # total unrealized P&L on full position
    unrealized_pnl_pct: float   # as a percentage of total cost
    break_even_price: float     # == cost_basis (for clarity in the UI)


def compute_metrics(cost_basis: float, current_price: float, shares: float) -> ProfitMetrics:
    total_cost = cost_basis * shares
    unrealized = (current_price - cost_basis) * shares
    pct = (unrealized / total_cost * 100) if total_cost else 0.0
    return ProfitMetrics(
        cost_basis=cost_basis,
        current_price=current_price,
        shares_held=shares,
        unrealized_pnl=unrealized,
        unrealized_pnl_pct=pct,
        break_even_price=cost_basis,
    )


def required_price_for_target(cost_basis: float, shares_to_sell: float, profit_target: float) -> float:
    """Return the sell price needed so that selling *shares_to_sell* nets *profit_target*.

    profit = (sell_price - cost_basis) * shares_to_sell
    => sell_price = cost_basis + profit_target / shares_to_sell
    """
    if shares_to_sell <= 0:
        raise ValueError("shares_to_sell must be positive")
    return cost_basis + profit_target / shares_to_sell


def shares_needed_at_price(cost_basis: float, sell_price: float, profit_target: float) -> float:
    """Return shares needed to net *profit_target* when selling at *sell_price*.

    shares = profit_target / (sell_price - cost_basis)
    """
    gain_per_share = sell_price - cost_basis
    if gain_per_share <= 0:
        raise ValueError("sell_price must exceed cost_basis to generate a profit")
    return profit_target / gain_per_share


def profit_at(cost_basis: float, sell_price: float, shares_to_sell: float) -> float:
    return (sell_price - cost_basis) * shares_to_sell
