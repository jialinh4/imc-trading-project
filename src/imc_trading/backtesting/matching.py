from __future__ import annotations

from dataclasses import dataclass
from typing import List

from datamodel import OrderDepth

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
    This is the first new execution module that should replace the legacy
    _execute_buy_order / _execute_sell_order behavior.
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
    Placeholder for the cross-timestamp passive execution model.
    Current notebook behavior uses same-timestamp trade history in an optimistic way.
    This class exists so the project can migrate to the target architecture without
    changing the strategy API again.
    """

    def __init__(self, order_manager: OrderManager) -> None:
        self.order_manager = order_manager

    def match_resting_order(self, order: ManagedOrder, trade_flow: list, ts: int) -> List[Fill]:
        return []
