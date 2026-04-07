from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    NEW = "NEW"
    ACTIVE = "ACTIVE"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"


class TimeInForce(str, Enum):
    IOC = "IOC"
    GFD = "GFD"


@dataclass
class ManagedOrder:
    order_id: str
    symbol: str
    side: Side
    price: float
    original_qty: int
    remaining_qty: int
    filled_qty: int = 0
    avg_fill_price: float = 0.0
    status: OrderStatus = OrderStatus.NEW
    created_ts: int = 0
    last_update_ts: int = 0
    tif: TimeInForce = TimeInForce.GFD
    is_aggressive: bool = False
    queue_ahead_qty: int = 0

    def apply_fill(self, qty: int, price: float, ts: int) -> None:
        if qty <= 0 or qty > self.remaining_qty:
            raise ValueError("Invalid fill quantity.")
        total_notional = self.avg_fill_price * self.filled_qty + price * qty
        self.filled_qty += qty
        self.remaining_qty -= qty
        self.avg_fill_price = total_notional / self.filled_qty
        self.last_update_ts = ts
        self.status = OrderStatus.FILLED if self.remaining_qty == 0 else OrderStatus.PARTIAL


class OrderManager:
    """
    First implementation target:
    1. Keep this module independent from strategy code.
    2. Preserve enough state to support resting orders across timestamps.
    3. Replace legacy immediate-forget execution once matcher integration is ready.
    """

    def __init__(self) -> None:
        self._counter = 0
        self.orders: Dict[str, ManagedOrder] = {}
        self.resting_bids: Dict[str, List[str]] = {}
        self.resting_asks: Dict[str, List[str]] = {}

    def _next_order_id(self) -> str:
        self._counter += 1
        return f"ord_{self._counter:08d}"

    def submit_order(
        self,
        symbol: str,
        side: Side,
        price: float,
        quantity: int,
        ts: int,
        tif: TimeInForce = TimeInForce.GFD,
        is_aggressive: bool = False,
        queue_ahead_qty: int = 0,
    ) -> ManagedOrder:
        order = ManagedOrder(
            order_id=self._next_order_id(),
            symbol=symbol,
            side=side,
            price=price,
            original_qty=quantity,
            remaining_qty=quantity,
            status=OrderStatus.ACTIVE,
            created_ts=ts,
            last_update_ts=ts,
            tif=tif,
            is_aggressive=is_aggressive,
            queue_ahead_qty=queue_ahead_qty,
        )
        self.orders[order.order_id] = order
        return order

    def fill(self, order_id: str, qty: int, price: float, ts: int) -> ManagedOrder:
        order = self.orders[order_id]
        order.apply_fill(qty, price, ts)
        return order

    def cancel(self, order_id: str, ts: int) -> int:
        order = self.orders[order_id]
        if order.status in {OrderStatus.ACTIVE, OrderStatus.PARTIAL, OrderStatus.NEW}:
            remaining = order.remaining_qty
            order.status = OrderStatus.CANCELED
            order.last_update_ts = ts
            return remaining
        return 0

    def expire_all(self, ts: int) -> None:
        for order in self.orders.values():
            if order.tif == TimeInForce.GFD and order.status in {OrderStatus.ACTIVE, OrderStatus.PARTIAL, OrderStatus.NEW}:
                order.status = OrderStatus.EXPIRED
                order.last_update_ts = ts

    def get_active_orders(self, symbol: Optional[str] = None) -> List[ManagedOrder]:
        active = [o for o in self.orders.values() if o.status in {OrderStatus.NEW, OrderStatus.ACTIVE, OrderStatus.PARTIAL}]
        if symbol is not None:
            active = [o for o in active if o.symbol == symbol]
        return active

    def get_resting_orders(self, symbol: str) -> List[ManagedOrder]:
        return [o for o in self.get_active_orders(symbol) if not o.is_aggressive and o.remaining_qty > 0]
