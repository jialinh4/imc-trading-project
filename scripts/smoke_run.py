from __future__ import annotations

from pathlib import Path

import pandas as pd

from imc_trading.backtesting.legacy_backtester import Backtester
from imc_trading.config import LISTINGS, POSITION_LIMITS
from imc_trading.fair_value import calculate_amethysts_fair, calculate_starfruit_fair
from imc_trading.strategy.trader import Product, Trader


def build_market_data() -> pd.DataFrame:
    rows = []
    for timestamp in [0, 100]:
        rows.append(
            {
                "timestamp": timestamp,
                "product": Product.AMETHYSTS,
                "bid_price_1": 9998,
                "bid_volume_1": 10,
                "bid_price_2": 9997,
                "bid_volume_2": 8,
                "bid_price_3": 9996,
                "bid_volume_3": 5,
                "ask_price_1": 10002,
                "ask_volume_1": 10,
                "ask_price_2": 10003,
                "ask_volume_2": 8,
                "ask_price_3": 10004,
                "ask_volume_3": 5,
            }
        )
        rows.append(
            {
                "timestamp": timestamp,
                "product": Product.STARFRUIT,
                "bid_price_1": 4998,
                "bid_volume_1": 20,
                "bid_price_2": 4997,
                "bid_volume_2": 10,
                "bid_price_3": 4996,
                "bid_volume_3": 5,
                "ask_price_1": 5002,
                "ask_volume_1": 20,
                "ask_price_2": 5003,
                "ask_volume_2": 10,
                "ask_price_3": 5004,
                "ask_volume_3": 5,
            }
        )
    return pd.DataFrame(rows)


def build_trade_history() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"timestamp": 0, "symbol": Product.AMETHYSTS, "price": 10002, "quantity": 2, "buyer": "", "seller": ""},
            {"timestamp": 100, "symbol": Product.STARFRUIT, "price": 5002, "quantity": 1, "buyer": "", "seller": ""},
        ]
    )


def main() -> None:
    market_data = build_market_data()
    trade_history = build_trade_history()
    fair_calculations = {
        Product.AMETHYSTS: calculate_amethysts_fair,
        Product.STARFRUIT: calculate_starfruit_fair,
    }
    log_path = Path("outputs") / "smoke_backtest.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    backtester = Backtester(
        trader=Trader(),
        listings=LISTINGS,
        position_limit=POSITION_LIMITS,
        fair_marks=fair_calculations,
        market_data=market_data,
        trade_history=trade_history,
        file_name=str(log_path),
    )
    backtester.run()

    print("Smoke backtest finished successfully.")
    print(f"Log written to: {log_path}")
    print(f"Final pnl: {backtester.pnl}")
    print(f"Final positions: {backtester.current_position}")


if __name__ == "__main__":
    main()
