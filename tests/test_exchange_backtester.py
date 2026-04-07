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


def test_exchange_backtester_executes_aggressive_order(tmp_path) -> None:
    trader = StaticTrader({0: {Product.AMETHYSTS: [Order(Product.AMETHYSTS, 10002, 2)]}, 100: {}})
    backtester = ExchangeBacktester(
        trader=trader,
        listings={Product.AMETHYSTS: LISTINGS[Product.AMETHYSTS]},
        position_limit={Product.AMETHYSTS: POSITION_LIMITS[Product.AMETHYSTS]},
        fair_marks={Product.AMETHYSTS: lambda *_args, **_kwargs: 10000},
        market_data=_market_data(),
        trade_history=pd.DataFrame(columns=["timestamp", "symbol", "price", "quantity", "buyer", "seller"]),
        file_name=str(tmp_path / "exchange.log"),
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
