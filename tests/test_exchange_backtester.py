from __future__ import annotations

import pandas as pd

from datamodel import Order
from imc_trading.backtesting.exchange_backtester import ExchangeBacktester
from imc_trading.backtesting.order_manager import OrderStatus
from imc_trading.config import LISTINGS, POSITION_LIMITS
from imc_trading.strategy.trader import Product


class StaticTrader:
    def __init__(self, schedule):
        self.schedule = schedule

    def run(self, state):
        return self.schedule.get(state.timestamp, {}), 1, ""


class CapturingTrader:
    def __init__(self, schedule):
        self.schedule = schedule
        self.seen_states = []

    def run(self, state):
        self.seen_states.append(state)
        return self.schedule.get(state.timestamp, {}), 1, ""


def _market_data() -> pd.DataFrame:
    rows = []
    for timestamp in [0, 100]:
        rows.append(
            {
                "timestamp": timestamp,
                "product": Product.AMETHYSTS,
                "bid_price_1": 9998,
                "bid_volume_1": 10,
                "bid_price_2": 9997,
                "bid_volume_2": 5,
                "bid_price_3": 9996,
                "bid_volume_3": 3,
                "ask_price_1": 10002,
                "ask_volume_1": 10,
                "ask_price_2": 10003,
                "ask_volume_2": 5,
                "ask_price_3": 10004,
                "ask_volume_3": 3,
            }
        )
    return pd.DataFrame(rows)


def test_exchange_backtester_executes_aggressive_order() -> None:
    trader = StaticTrader({0: {Product.AMETHYSTS: [Order(Product.AMETHYSTS, 10002, 2)]}, 100: {}})
    backtester = ExchangeBacktester(
        trader=trader,
        listings={Product.AMETHYSTS: LISTINGS[Product.AMETHYSTS]},
        position_limit={Product.AMETHYSTS: POSITION_LIMITS[Product.AMETHYSTS]},
        fair_marks={Product.AMETHYSTS: lambda *_args, **_kwargs: 10000},
        market_data=_market_data(),
        trade_history=pd.DataFrame(columns=["timestamp", "symbol", "price", "quantity", "buyer", "seller"]),
    )

    backtester.run()

    assert backtester.current_position[Product.AMETHYSTS] == 2
    assert backtester.cash[Product.AMETHYSTS] == -20004
    assert len(backtester.order_manager.orders) == 1
    only_order = next(iter(backtester.order_manager.orders.values()))
    assert only_order.status == OrderStatus.FILLED


def test_exchange_backtester_keeps_passive_gfd_order_when_persistent() -> None:
    trader = StaticTrader({0: {Product.AMETHYSTS: [Order(Product.AMETHYSTS, 10000, 2)]}, 100: {}})
    backtester = ExchangeBacktester(
        trader=trader,
        listings={Product.AMETHYSTS: LISTINGS[Product.AMETHYSTS]},
        position_limit={Product.AMETHYSTS: POSITION_LIMITS[Product.AMETHYSTS]},
        fair_marks={Product.AMETHYSTS: lambda *_args, **_kwargs: 10000},
        market_data=_market_data(),
        trade_history=pd.DataFrame(columns=["timestamp", "symbol", "price", "quantity", "buyer", "seller"]),
        resting_mode="persistent",
    )

    backtester.run()

    assert len(backtester.order_manager.orders) == 1
    only_order = next(iter(backtester.order_manager.orders.values()))
    assert only_order.status == OrderStatus.EXPIRED
    assert only_order.remaining_qty == 2


def test_exchange_backtester_fills_resting_order_on_next_timestamp() -> None:
    trader = StaticTrader({0: {Product.AMETHYSTS: [Order(Product.AMETHYSTS, 10000, 3)]}, 100: {}})
    trade_history = pd.DataFrame(
        [
            {
                "timestamp": 100,
                "symbol": Product.AMETHYSTS,
                "price": 9999,
                "quantity": 2,
                "buyer": "A",
                "seller": "B",
            },
            {
                "timestamp": 100,
                "symbol": Product.AMETHYSTS,
                "price": 10000,
                "quantity": 2,
                "buyer": "C",
                "seller": "D",
            },
        ]
    )
    backtester = ExchangeBacktester(
        trader=trader,
        listings={Product.AMETHYSTS: LISTINGS[Product.AMETHYSTS]},
        position_limit={Product.AMETHYSTS: POSITION_LIMITS[Product.AMETHYSTS]},
        fair_marks={Product.AMETHYSTS: lambda *_args, **_kwargs: 10000},
        market_data=_market_data(),
        trade_history=trade_history,
        resting_mode="persistent",
    )

    backtester.run()

    only_order = next(iter(backtester.order_manager.orders.values()))
    assert only_order.status == OrderStatus.FILLED
    assert backtester.current_position[Product.AMETHYSTS] == 3
    assert backtester.cash[Product.AMETHYSTS] == -30000


def test_exchange_backtester_passes_incremental_own_trades_to_next_callback() -> None:
    trader = CapturingTrader({0: {Product.AMETHYSTS: [Order(Product.AMETHYSTS, 10000, 2)]}, 100: {}})
    trade_history = pd.DataFrame(
        [
            {
                "timestamp": 100,
                "symbol": Product.AMETHYSTS,
                "price": 10000,
                "quantity": 2,
                "buyer": "A",
                "seller": "B",
            }
        ]
    )
    backtester = ExchangeBacktester(
        trader=trader,
        listings={Product.AMETHYSTS: LISTINGS[Product.AMETHYSTS]},
        position_limit={Product.AMETHYSTS: POSITION_LIMITS[Product.AMETHYSTS]},
        fair_marks={Product.AMETHYSTS: lambda *_args, **_kwargs: 10000},
        market_data=_market_data(),
        trade_history=trade_history,
        resting_mode="persistent",
    )

    backtester.run()

    assert len(trader.seen_states) == 2
    second_state = trader.seen_states[1]
    assert Product.AMETHYSTS in second_state.own_trades
    assert len(second_state.own_trades[Product.AMETHYSTS]) == 1
    own_trade = second_state.own_trades[Product.AMETHYSTS][0]
    assert own_trade.price == 10000
    assert own_trade.quantity == 2
    assert second_state.position[Product.AMETHYSTS] == 2


def test_exchange_backtester_simple_queue_delays_passive_fill() -> None:
    class QueueAwareTrader:
        def run(self, state):
            if state.timestamp == 0:
                return {Product.AMETHYSTS: [Order(Product.AMETHYSTS, 9998, 3)]}, 1, ""
            return {}, 1, ""

    trade_history = pd.DataFrame(
        [
            {
                "timestamp": 100,
                "symbol": Product.AMETHYSTS,
                "price": 9998,
                "quantity": 4,
                "buyer": "A",
                "seller": "B",
            }
        ]
    )

    backtester = ExchangeBacktester(
        trader=QueueAwareTrader(),
        listings={Product.AMETHYSTS: LISTINGS[Product.AMETHYSTS]},
        position_limit={Product.AMETHYSTS: POSITION_LIMITS[Product.AMETHYSTS]},
        fair_marks={Product.AMETHYSTS: lambda *_args, **_kwargs: 10000},
        market_data=_market_data(),
        trade_history=trade_history,
        resting_mode="persistent",
        queue_model="simple",
    )

    backtester.run()

    only_order = next(iter(backtester.order_manager.orders.values()))
    assert only_order.remaining_qty == 3
    assert only_order.queue_ahead_qty == 6
    assert backtester.current_position[Product.AMETHYSTS] == 0


def test_exchange_backtester_none_queue_fills_same_trade_flow_immediately() -> None:
    class QueueAwareTrader:
        def run(self, state):
            if state.timestamp == 0:
                return {Product.AMETHYSTS: [Order(Product.AMETHYSTS, 9998, 3)]}, 1, ""
            return {}, 1, ""

    trade_history = pd.DataFrame(
        [
            {
                "timestamp": 100,
                "symbol": Product.AMETHYSTS,
                "price": 9998,
                "quantity": 4,
                "buyer": "A",
                "seller": "B",
            }
        ]
    )

    backtester = ExchangeBacktester(
        trader=QueueAwareTrader(),
        listings={Product.AMETHYSTS: LISTINGS[Product.AMETHYSTS]},
        position_limit={Product.AMETHYSTS: POSITION_LIMITS[Product.AMETHYSTS]},
        fair_marks={Product.AMETHYSTS: lambda *_args, **_kwargs: 10000},
        market_data=_market_data(),
        trade_history=trade_history,
        resting_mode="persistent",
        queue_model="none",
    )

    backtester.run()

    only_order = next(iter(backtester.order_manager.orders.values()))
    assert only_order.status == OrderStatus.FILLED
    assert backtester.current_position[Product.AMETHYSTS] == 3
