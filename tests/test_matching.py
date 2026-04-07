from datamodel import OrderDepth

from imc_trading.backtesting.matching import TakerMatcher
from imc_trading.backtesting.order_manager import OrderManager, OrderStatus, Side


def test_taker_matcher_executes_across_multiple_levels() -> None:
    manager = OrderManager()
    order = manager.submit_order(
        symbol="STARFRUIT",
        side=Side.BUY,
        price=101,
        quantity=7,
        ts=0,
        is_aggressive=True,
    )
    depth = OrderDepth(
        buy_orders={},
        sell_orders={100: -5, 101: -4, 102: -3},
    )

    matcher = TakerMatcher(manager)
    fills = matcher.match(order, depth, ts=1)

    assert [fill.fill_qty for fill in fills] == [5, 2]
    assert [fill.fill_price for fill in fills] == [100, 101]
    assert manager.orders[order.order_id].status == OrderStatus.FILLED
    assert depth.sell_orders == {101: -2, 102: -3}
