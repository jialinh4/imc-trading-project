from __future__ import annotations

from pathlib import Path

import pandas as pd

from datamodel import Order
from imc_trading.backtesting.exchange_backtester import ExchangeBacktester
from imc_trading.config import LISTINGS, POSITION_LIMITS
from imc_trading.strategy.trader import Product


class StaticTrader:
    def run(self, state):
        if state.timestamp == 0:
            return {Product.AMETHYSTS: [Order(Product.AMETHYSTS, 10002, 1)]}, 1, ""
        return {}, 1, ""


def build_market_data() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "timestamp": 0,
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
            },
            {
                "timestamp": 100,
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
            },
        ]
    )


def main() -> None:
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)

    backtester = ExchangeBacktester(
        trader=StaticTrader(),
        listings={Product.AMETHYSTS: LISTINGS[Product.AMETHYSTS]},
        position_limit={Product.AMETHYSTS: POSITION_LIMITS[Product.AMETHYSTS]},
        fair_marks={Product.AMETHYSTS: lambda *_args, **_kwargs: 10000},
        market_data=build_market_data(),
        trade_history=pd.DataFrame(columns=["timestamp", "symbol", "price", "quantity", "buyer", "seller"]),
        file_name=str(out_dir / "exchange_smoke_backtest.log"),
    )
    backtester.run()
    print("Exchange smoke backtest finished successfully.")
    print(f"Final pnl: {backtester.pnl}")
    print(f"Final positions: {backtester.current_position}")


if __name__ == "__main__":
    main()
