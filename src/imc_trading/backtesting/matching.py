from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from datamodel import OrderDepth, Trade

from .order_manager import ManagedOrder, OrderManager, Side


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
    Cross-timestamp passive matcher.

    Phase 2 scope:
    - use trade flow at later timestamps to fill resting GFD orders
    - support queue_model='none' or 'simple'
    - fill passive orders at the resting order price
    """

    def __init__(self, order_manager: OrderManager) -> None:
        self.order_manager = order_manager

    def match_resting_order(
        self,
        order: ManagedOrder,
        trade_flow: Iterable[Trade],
        ts: int,
        queue_model: str = "none",
    ) -> List[Fill]:
        fills: List[Fill] = []
        if order.remaining_qty <= 0:
            return fills

        for trade in trade_flow:
            if trade.symbol != order.symbol or order.remaining_qty <= 0:
                continue
            marketable_volume = self._marketable_volume(order, trade)
            if marketable_volume <= 0:
                continue

            if queue_model == "simple" and order.queue_ahead_qty > 0:
                absorbed = min(marketable_volume, order.queue_ahead_qty)
                order.queue_ahead_qty -= absorbed
                marketable_volume -= absorbed

            if marketable_volume <= 0:
                continue

            fill_qty = min(marketable_volume, order.remaining_qty)
            self.order_manager.fill(order.order_id, fill_qty, order.price, ts)
            fills.append(Fill(order.order_id, order.symbol, order.price, fill_qty, "maker", ts))

        return fills

    def _marketable_volume(self, order: ManagedOrder, trade: Trade) -> int:
        if order.side == Side.BUY and trade.price <= order.price:
            return int(trade.quantity)
        if order.side == Side.SELL and trade.price >= order.price:
            return int(trade.quantity)
        return 0
