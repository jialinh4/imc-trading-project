from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

from datamodel import OrderDepth, Trade

from .order_manager import ManagedOrder, OrderManager, Side
from .queue_tracker import QueueModel, QueueTracker


@dataclass
class Fill:
    order_id: str
    symbol: str
    fill_price: float
    fill_qty: int
    side: str
    timestamp: int


class TakerMatcher:
    """
    Deterministic matcher for aggressive orders.
    """

    def __init__(self, order_manager: OrderManager) -> None:
        self.order_manager = order_manager

    def match(self, order: ManagedOrder, order_depth: OrderDepth, ts: int) -> List[Fill]:
        fills: List[Fill] = []
        if order.side == Side.BUY:
            for price in sorted(order_depth.sell_orders.keys()):
                if order.remaining_qty <= 0 or price > order.price:
                    break
                available = abs(order_depth.sell_orders[price])
                qty = min(order.remaining_qty, available)
                if qty <= 0:
                    continue
                self.order_manager.fill(order.order_id, qty, price, ts)
                order_depth.sell_orders[price] += qty
                if order_depth.sell_orders[price] == 0:
                    del order_depth.sell_orders[price]
                fills.append(Fill(order.order_id, order.symbol, price, qty, "taker", ts))
        else:
            for price in sorted(order_depth.buy_orders.keys(), reverse=True):
                if order.remaining_qty <= 0 or price < order.price:
                    break
                available = abs(order_depth.buy_orders[price])
                qty = min(order.remaining_qty, available)
                if qty <= 0:
                    continue
                self.order_manager.fill(order.order_id, qty, price, ts)
                order_depth.buy_orders[price] -= qty
                if order_depth.buy_orders[price] == 0:
                    del order_depth.buy_orders[price]
                fills.append(Fill(order.order_id, order.symbol, price, qty, "taker", ts))
        return fills


class MakerMatcher:
    """
    Queue-aware passive matcher.

    Phase 3 scope:
    - trade flow is consumed globally across multiple resting orders
    - better prices receive priority before worse prices
    - FIFO is respected within the same price level
    - queue_model='simple' consumes queue_ahead_qty before our order can fill
    """

    def __init__(self, order_manager: OrderManager, queue_tracker: QueueTracker | None = None) -> None:
        self.order_manager = order_manager
        self.queue_tracker = queue_tracker or QueueTracker()

    def match_resting_orders(
        self,
        orders: Sequence[ManagedOrder],
        trade_flow: Iterable[Trade],
        ts: int,
        queue_model: str = "simple",
    ) -> List[Fill]:
        if not orders:
            return []

        trades = list(trade_flow)
        remaining_by_trade = [int(trade.quantity) for trade in trades]
        fills: List[Fill] = []

        for order in orders:
            if order.remaining_qty <= 0:
                continue
            for idx, trade in enumerate(trades):
                if order.remaining_qty <= 0:
                    break
                if trade.symbol != order.symbol:
                    continue
                if remaining_by_trade[idx] <= 0:
                    continue
                if not self._trade_is_marketable_for_order(order, trade):
                    continue

                remaining_after_queue = self.queue_tracker.apply_queue_ahead(
                    order=order,
                    marketable_volume=remaining_by_trade[idx],
                    queue_model=queue_model,
                )
                remaining_by_trade[idx] = remaining_after_queue
                if remaining_after_queue <= 0:
                    continue

                fill_qty = min(remaining_after_queue, order.remaining_qty)
                self.order_manager.fill(order.order_id, fill_qty, order.price, ts)
                remaining_by_trade[idx] -= fill_qty
                fills.append(Fill(order.order_id, order.symbol, order.price, fill_qty, "maker", ts))

        return fills

    def match_resting_order(
        self,
        order: ManagedOrder,
        trade_flow: Iterable[Trade],
        ts: int,
        queue_model: str = "simple",
    ) -> List[Fill]:
        return self.match_resting_orders([order], trade_flow, ts, queue_model=queue_model)

    def _trade_is_marketable_for_order(self, order: ManagedOrder, trade: Trade) -> bool:
        if order.side == Side.BUY:
            return trade.price <= order.price
        return trade.price >= order.price
