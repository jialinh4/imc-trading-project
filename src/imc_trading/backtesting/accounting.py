from __future__ import annotations

from dataclasses import asdict, dataclass
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

    def to_dict(self) -> Dict[str, float | int | str]:
        return asdict(self)


class AccountingEngine:
    """
    Per-symbol accounting with realized/unrealized split.

    Phase 4 scope:
    - maintain per-symbol mark history
    - expose portfolio-level snapshots per timestamp
    - provide structured history for enhanced backtester logging
    """

    def __init__(self) -> None:
        self.realized_pnl: Dict[str, float] = {}
        self.position: Dict[str, int] = {}
        self.avg_entry_price: Dict[str, float] = {}
        self.cash: Dict[str, float] = {}
        self.history: List[PnLSnapshot] = []
        self.portfolio_history: List[PnLSnapshot] = []

    def _ensure_symbol(self, symbol: str) -> None:
        self.realized_pnl.setdefault(symbol, 0.0)
        self.position.setdefault(symbol, 0)
        self.avg_entry_price.setdefault(symbol, 0.0)
        self.cash.setdefault(symbol, 0.0)

    def record_fill(self, fill: Fill, signed_qty: int) -> None:
        symbol = fill.symbol
        self._ensure_symbol(symbol)

        old_pos = self.position[symbol]
        old_avg = self.avg_entry_price[symbol]
        qty = signed_qty
        price = float(fill.fill_price)

        self.cash[symbol] -= price * qty

        if old_pos == 0 or old_pos * qty > 0:
            new_pos = old_pos + qty
            total_qty = abs(old_pos) + abs(qty)
            if total_qty > 0:
                self.avg_entry_price[symbol] = (old_avg * abs(old_pos) + price * abs(qty)) / total_qty
            self.position[symbol] = new_pos
            return

        closing_qty = min(abs(old_pos), abs(qty))
        if old_pos > 0:
            self.realized_pnl[symbol] += closing_qty * (price - old_avg)
        else:
            self.realized_pnl[symbol] += closing_qty * (old_avg - price)

        new_pos = old_pos + qty
        self.position[symbol] = new_pos
        if new_pos == 0:
            self.avg_entry_price[symbol] = 0.0
        elif old_pos * new_pos > 0:
            self.avg_entry_price[symbol] = old_avg
        else:
            self.avg_entry_price[symbol] = price

    def mark(
        self,
        timestamp: int,
        symbol: str,
        order_depth: OrderDepth,
        fair_value: float,
        slippage: float = 0.0,
        num_fills: int = 0,
    ) -> PnLSnapshot:
        self._ensure_symbol(symbol)
        if not order_depth.buy_orders or not order_depth.sell_orders:
            raise ValueError(f"Cannot mark pnl for {symbol} without both bid and ask levels.")

        best_ask = min(order_depth.sell_orders.keys())
        best_bid = max(order_depth.buy_orders.keys())
        mid = (best_ask + best_bid) / 2
        position = self.position[symbol]
        cash = self.cash[symbol]
        entry = self.avg_entry_price[symbol]
        realized = self.realized_pnl[symbol]

        unrealized_mid = position * (mid - entry)
        unrealized_fair = position * (fair_value - entry)
        if position > 0:
            liquidation_price = best_bid - slippage
        elif position < 0:
            liquidation_price = best_ask + slippage
        else:
            liquidation_price = mid
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

    def mark_portfolio(self, timestamp: int) -> PnLSnapshot:
        snapshots = [snap for snap in self.history if snap.timestamp == timestamp]
        portfolio_snapshot = PnLSnapshot(
            timestamp=timestamp,
            symbol="PORTFOLIO",
            realized_pnl=sum(s.realized_pnl for s in snapshots),
            unrealized_pnl_mid=sum(s.unrealized_pnl_mid for s in snapshots),
            unrealized_pnl_fair=sum(s.unrealized_pnl_fair for s in snapshots),
            total_pnl_mid=sum(s.total_pnl_mid for s in snapshots),
            total_pnl_fair=sum(s.total_pnl_fair for s in snapshots),
            total_pnl_liquidation=sum(s.total_pnl_liquidation for s in snapshots),
            position=sum(s.position for s in snapshots),
            cash=sum(s.cash for s in snapshots),
            num_fills=sum(s.num_fills for s in snapshots),
        )
        self.portfolio_history.append(portfolio_snapshot)
        return portfolio_snapshot

    def portfolio_pnl(self, timestamp: int) -> PnLSnapshot:
        existing = [snap for snap in self.portfolio_history if snap.timestamp == timestamp]
        if existing:
            return existing[-1]
        return self.mark_portfolio(timestamp)

    def get_history(self, symbol: str | None = None) -> List[PnLSnapshot]:
        history = list(self.history)
        if symbol is None:
            return history
        return [snapshot for snapshot in history if snapshot.symbol == symbol]

    def get_portfolio_history(self) -> List[PnLSnapshot]:
        return list(self.portfolio_history)

    def get_latest_symbol_snapshot(self, symbol: str) -> PnLSnapshot | None:
        history = self.get_history(symbol=symbol)
        return history[-1] if history else None
