from datamodel import OrderDepth, Trade

from imc_trading.backtesting.matching import MakerMatcher, TakerMatcher
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


def test_maker_matcher_fills_resting_order_on_later_trade_flow() -> None:
    manager = OrderManager()
    order = manager.submit_order(
        symbol="STARFRUIT",
        side=Side.BUY,
        price=100,
        quantity=6,
        ts=0,
        is_aggressive=False,
    )
    manager._add_resting_order(order)

    trade_flow = [
        Trade(symbol="STARFRUIT", price=101, quantity=2, buyer="", seller="", timestamp=100),
        Trade(symbol="STARFRUIT", price=100, quantity=4, buyer="", seller="", timestamp=100),
        Trade(symbol="STARFRUIT", price=99, quantity=3, buyer="", seller="", timestamp=100),
    ]

    matcher = MakerMatcher(manager)
    fills = matcher.match_resting_order(order, trade_flow, ts=100, queue_model="none")

    assert [fill.fill_qty for fill in fills] == [4, 2]
    assert [fill.fill_price for fill in fills] == [100, 100]
    assert manager.orders[order.order_id].status == OrderStatus.FILLED


def test_queue_simple_absorbs_ahead_volume_before_filling() -> None:
    manager = OrderManager()
    order = manager.submit_order(
        symbol="STARFRUIT",
        side=Side.BUY,
        price=100,
        quantity=5,
        ts=0,
        is_aggressive=False,
        queue_ahead_qty=3,
    )
    manager._add_resting_order(order)

    trade_flow = [
        Trade(symbol="STARFRUIT", price=100, quantity=2, buyer="", seller="", timestamp=100),
        Trade(symbol="STARFRUIT", price=100, quantity=4, buyer="", seller="", timestamp=100),
    ]

    fills = MakerMatcher(manager).match_resting_order(order, trade_flow, ts=100, queue_model="simple")

    assert [fill.fill_qty for fill in fills] == [3]
    assert manager.orders[order.order_id].remaining_qty == 2
    assert manager.orders[order.order_id].queue_ahead_qty == 0


def test_maker_matcher_respects_price_priority_across_orders() -> None:
    manager = OrderManager()
    buy_best = manager.submit_order("STARFRUIT", Side.BUY, 100, 2, ts=0, is_aggressive=False)
    buy_worse = manager.submit_order("STARFRUIT", Side.BUY, 99, 2, ts=0, is_aggressive=False)

    trade_flow = [Trade(symbol="STARFRUIT", price=99, quantity=3, buyer="", seller="", timestamp=100)]

    matcher = MakerMatcher(manager)
    fills = matcher.match_resting_orders([buy_best, buy_worse], trade_flow, ts=100, queue_model="none")

    assert [(fill.order_id, fill.fill_qty) for fill in fills] == [
        (buy_best.order_id, 2),
        (buy_worse.order_id, 1),
    ]
    assert manager.orders[buy_best.order_id].status == OrderStatus.FILLED
    assert manager.orders[buy_worse.order_id].remaining_qty == 1
