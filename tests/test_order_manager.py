from datamodel import Order, OrderDepth

from imc_trading.backtesting.order_manager import OrderManager, OrderStatus, Side, TimeInForce


def test_order_lifecycle_submit_fill_cancel() -> None:
    manager = OrderManager()
    managed = manager.submit_order(
        symbol="STARFRUIT",
        side=Side.BUY,
        price=100,
        quantity=10,
        ts=0,
    )
    assert managed.status == OrderStatus.ACTIVE
    assert managed.remaining_qty == 10
    manager.fill(managed.order_id, qty=4, price=100, ts=1)
    assert managed.status == OrderStatus.PARTIAL
    assert managed.remaining_qty == 6
    canceled = manager.cancel(managed.order_id, ts=2)
    assert canceled == 6
    assert managed.status == OrderStatus.CANCELED


def test_submit_raw_order_detects_aggression() -> None:
    manager = OrderManager()
    depth = OrderDepth(buy_orders={99: 5}, sell_orders={101: -5})
    raw = Order("STARFRUIT", 101, 3)
    managed = manager.submit_raw_order(raw, ts=0, order_depth=depth)
    assert managed.is_aggressive is True
    assert managed.side == Side.BUY
    assert managed.tif == TimeInForce.GFD


def test_submit_raw_order_sets_queue_ahead_when_joining_existing_level() -> None:
    manager = OrderManager()
    depth = OrderDepth(buy_orders={100: 7, 99: 4}, sell_orders={102: -5, 103: -3})

    managed = manager.submit_raw_order(Order("STARFRUIT", 100, 2), ts=0, order_depth=depth)

    assert managed.is_aggressive is False
    assert managed.queue_ahead_qty == 7


def test_submit_raw_order_sets_zero_queue_when_improving_best_level() -> None:
    manager = OrderManager()
    depth = OrderDepth(buy_orders={100: 7, 99: 4}, sell_orders={102: -5, 103: -3})

    managed = manager.submit_raw_order(Order("STARFRUIT", 101, 2), ts=0, order_depth=depth)

    assert managed.is_aggressive is False
    assert managed.queue_ahead_qty == 0
