from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Optional

from datamodel import OrderDepth

if TYPE_CHECKING:
    from .order_manager import ManagedOrder


class QueueModel(str, Enum):
    NONE = "none"
    SIMPLE = "simple"
    PRO_RATA = "pro_rata"


class QueueTracker:
    """
    Lightweight queue approximation utilities.

    Phase 3 scope:
    - estimate queue ahead at submission time
    - consume queue ahead before passive fills when queue_model='simple'
    - keep a compatibility path for queue_model='none'
    """

    def estimate_queue_ahead_qty(
        self,
        side: str,
        price: float,
        order_depth: Optional[OrderDepth],
        is_aggressive: bool,
    ) -> int:
        if order_depth is None or is_aggressive:
            return 0

        if side == "BUY":
            visible_at_price = max(int(order_depth.buy_orders.get(price, 0)), 0)
            if visible_at_price > 0:
                return visible_at_price
            best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
            if best_bid is None or price > best_bid:
                return 0
            return 0

        visible_at_price = max(abs(int(order_depth.sell_orders.get(price, 0))), 0)
        if visible_at_price > 0:
            return visible_at_price
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
        if best_ask is None or price < best_ask:
            return 0
        return 0

    def apply_queue_ahead(
        self,
        order: ManagedOrder,
        marketable_volume: int,
        queue_model: str | QueueModel,
    ) -> int:
        model = QueueModel(queue_model)
        if model == QueueModel.NONE:
            return marketable_volume
        if model == QueueModel.PRO_RATA:
            raise NotImplementedError("queue_model='pro_rata' is reserved for a later phase.")

        if marketable_volume <= 0:
            return 0
        if order.queue_ahead_qty <= 0:
            return marketable_volume

        absorbed = min(marketable_volume, order.queue_ahead_qty)
        order.queue_ahead_qty -= absorbed
        return marketable_volume - absorbed
