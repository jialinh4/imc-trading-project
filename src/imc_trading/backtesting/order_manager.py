from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from datamodel import Order, OrderDepth


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
    Order lifecycle + resting order registry.

    Phase 1 scope:
    - persistent identity and order state
    - aggressive/passive detection against current book
    - basic resting order retention for GFD orders
    - symbol-level cancel/replace helper for backward-compatible strategy API
    """

    ACTIVE_STATUSES = {OrderStatus.NEW, OrderStatus.ACTIVE, OrderStatus.PARTIAL}

    def __init__(self) -> None:
        self._counter = 0
        self.orders: Dict[str, ManagedOrder] = {}
        self.resting_bids: Dict[str, List[str]] = {}
        self.resting_asks: Dict[str, List[str]] = {}

    def _next_order_id(self) -> str:
        self._counter += 1
        return f"ord_{self._counter:08d}"

    def _infer_side(self, quantity: int) -> Side:
        if quantity == 0:
            raise ValueError("Order quantity must be non-zero.")
        return Side.BUY if quantity > 0 else Side.SELL

    def _detect_aggressive(self, side: Side, price: float, order_depth: Optional[OrderDepth]) -> bool:
        if order_depth is None:
            return False
        if side == Side.BUY:
            return bool(order_depth.sell_orders) and price >= min(order_depth.sell_orders.keys())
        return bool(order_depth.buy_orders) and price <= max(order_depth.buy_orders.keys())

    def _estimate_queue_ahead_qty(
        self,
        side: Side,
        price: float,
        order_depth: Optional[OrderDepth],
        is_aggressive: bool,
    ) -> int:
        if order_depth is None or is_aggressive:
            return 0
        if side == Side.BUY:
            if price in order_depth.buy_orders:
                return max(int(order_depth.buy_orders[price]), 0)
            best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
            if best_bid is None or price > best_bid:
                return 0
            return 0
        if price in order_depth.sell_orders:
            return max(abs(int(order_depth.sell_orders[price])), 0)
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
        if best_ask is None or price < best_ask:
            return 0
        return 0

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

    def submit_raw_order(
        self,
        order: Order,
        ts: int,
        order_depth: Optional[OrderDepth] = None,
        tif: TimeInForce = TimeInForce.GFD,
    ) -> ManagedOrder:
        side = self._infer_side(order.quantity)
        quantity = abs(int(order.quantity))
        is_aggressive = self._detect_aggressive(side, float(order.price), order_depth)
        queue_ahead_qty = self._estimate_queue_ahead_qty(side, float(order.price), order_depth, is_aggressive)
        managed = self.submit_order(
            symbol=order.symbol,
            side=side,
            price=float(order.price),
            quantity=quantity,
            ts=ts,
            tif=tif,
            is_aggressive=is_aggressive,
            queue_ahead_qty=queue_ahead_qty,
        )
        if managed.tif == TimeInForce.GFD and not managed.is_aggressive:
            self._add_resting_order(managed)
        return managed

    def _add_resting_order(self, order: ManagedOrder) -> None:
        registry = self.resting_bids if order.side == Side.BUY else self.resting_asks
        registry.setdefault(order.symbol, []).append(order.order_id)

    def _remove_resting_order(self, order: ManagedOrder) -> None:
        registry = self.resting_bids if order.side == Side.BUY else self.resting_asks
        ids = registry.get(order.symbol, [])
        if order.order_id in ids:
            ids.remove(order.order_id)
        if not ids and order.symbol in registry:
            del registry[order.symbol]

    def fill(self, order_id: str, qty: int, price: float, ts: int) -> ManagedOrder:
        order = self.orders[order_id]
        order.apply_fill(qty, price, ts)
        if order.status == OrderStatus.FILLED:
            self._remove_resting_order(order)
        return order

    def cancel(self, order_id: str, ts: int) -> int:
        order = self.orders[order_id]
        if order.status in self.ACTIVE_STATUSES:
            remaining = order.remaining_qty
            order.status = OrderStatus.CANCELED
            order.last_update_ts = ts
            self._remove_resting_order(order)
            return remaining
        return 0

    def cancel_symbol_orders(self, symbol: str, ts: int) -> int:
        canceled = 0
        for order in list(self.get_resting_orders(symbol)):
            canceled += self.cancel(order.order_id, ts)
        return canceled

    def expire_all(self, ts: int) -> None:
        for order in self.orders.values():
            if order.tif == TimeInForce.GFD and order.status in self.ACTIVE_STATUSES:
                order.status = OrderStatus.EXPIRED
                order.last_update_ts = ts
                self._remove_resting_order(order)

    def get_active_orders(self, symbol: Optional[str] = None) -> List[ManagedOrder]:
        active = [o for o in self.orders.values() if o.status in self.ACTIVE_STATUSES]
        if symbol is not None:
            active = [o for o in active if o.symbol == symbol]
        return active

    def get_resting_orders(self, symbol: Optional[str] = None) -> List[ManagedOrder]:
        active = [o for o in self.orders.values() if o.status in self.ACTIVE_STATUSES and not o.is_aggressive and o.remaining_qty > 0]
        if symbol is not None:
            active = [o for o in active if o.symbol == symbol]
        return active
