from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from datamodel import OrderDepth

from .matching import Fill


@dataclass
class PnLSnapshot:
    timestamp: int
    symbol: str
    realized_pnl: float
    unrealized_pnl_mid: float
    unrealized_pnl_fair: float
    total_pnl_mid: float
    total_pnl_fair: float
    total_pnl_liquidation: float
    position: int
    cash: float
    num_fills: int


class AccountingEngine:
    """
    This module will replace legacy cash/pnl dictionaries.
    The first version keeps a clean interface even before the full migration is done.
    """

    def __init__(self) -> None:
        self.realized_pnl: Dict[str, float] = {}
        self.position: Dict[str, int] = {}
        self.avg_entry_price: Dict[str, float] = {}
        self.cash: Dict[str, float] = {}
        self.history: List[PnLSnapshot] = []

    def record_fill(self, fill: Fill, signed_qty: int) -> None:
        symbol = fill.symbol
        self.position.setdefault(symbol, 0)
        self.avg_entry_price.setdefault(symbol, 0.0)
        self.cash.setdefault(symbol, 0.0)
        self.realized_pnl.setdefault(symbol, 0.0)

        self.cash[symbol] -= fill.fill_price * signed_qty
        new_position = self.position[symbol] + signed_qty

        if self.position[symbol] == 0 or self.position[symbol] * signed_qty > 0:
            total_qty = abs(self.position[symbol]) + abs(signed_qty)
            if total_qty != 0:
                self.avg_entry_price[symbol] = (
                    self.avg_entry_price[symbol] * abs(self.position[symbol]) + fill.fill_price * abs(signed_qty)
                ) / total_qty
        self.position[symbol] = new_position

    def mark(
        self,
        timestamp: int,
        symbol: str,
        order_depth: OrderDepth,
        fair_value: float,
        slippage: float = 0.0,
        num_fills: int = 0,
    ) -> PnLSnapshot:
        best_ask = min(order_depth.sell_orders.keys())
        best_bid = max(order_depth.buy_orders.keys())
        mid = (best_ask + best_bid) / 2
        position = self.position.get(symbol, 0)
        cash = self.cash.get(symbol, 0.0)
        entry = self.avg_entry_price.get(symbol, 0.0)
        realized = self.realized_pnl.get(symbol, 0.0)

        unrealized_mid = position * (mid - entry)
        unrealized_fair = position * (fair_value - entry)
        liquidation_price = best_ask + slippage if position > 0 else best_bid - slippage
        total_liquidation = realized + position * (liquidation_price - entry)

        snapshot = PnLSnapshot(
            timestamp=timestamp,
            symbol=symbol,
            realized_pnl=realized,
            unrealized_pnl_mid=unrealized_mid,
            unrealized_pnl_fair=unrealized_fair,
            total_pnl_mid=realized + unrealized_mid,
            total_pnl_fair=realized + unrealized_fair,
            total_pnl_liquidation=total_liquidation,
            position=position,
            cash=cash,
            num_fills=num_fills,
        )
        self.history.append(snapshot)
        return snapshot

    def get_history(self) -> List[PnLSnapshot]:
        return list(self.history)
