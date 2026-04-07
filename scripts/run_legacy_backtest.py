from imc_trading.analysis.param_search import run_backtests
from imc_trading.backtesting.legacy_backtester import Backtester
from imc_trading.config import LISTINGS, POSITION_LIMITS
from imc_trading.fair_value import calculate_amethysts_fair, calculate_starfruit_fair
from imc_trading.io.log_parser import _process_data_
from imc_trading.strategy.trader import Trader, Product


def main() -> None:
    market_data, trade_history = _process_data_("round_1_clean_data.log")
    trader = Trader()
    fair_calculations = {
        Product.AMETHYSTS: calculate_amethysts_fair,
        Product.STARFRUIT: calculate_starfruit_fair,
    }
    backtester = Backtester(
        trader,
        LISTINGS,
        POSITION_LIMITS,
        fair_calculations,
        market_data,
        trade_history,
        "backtest_round1.log",
    )
    backtester.run()


if __name__ == "__main__":
    main()
