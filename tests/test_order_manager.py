from imc_trading.backtesting.order_manager import OrderManager, OrderStatus, Side, TimeInForce


def test_order_manager_lifecycle() -> None:
    manager = OrderManager()
    order = manager.submit_order(
        symbol="AMETHYSTS",
        side=Side.BUY,
        price=10000,
        quantity=10,
        ts=100,
        tif=TimeInForce.GFD,
    )

    assert order.status == OrderStatus.ACTIVE
    assert order.remaining_qty == 10

    manager.fill(order.order_id, qty=4, price=9999, ts=101)
    updated = manager.orders[order.order_id]
    assert updated.status == OrderStatus.PARTIAL
    assert updated.filled_qty == 4
    assert updated.remaining_qty == 6

    remaining = manager.cancel(order.order_id, ts=102)
    assert remaining == 6
    assert updated.status == OrderStatus.CANCELED
