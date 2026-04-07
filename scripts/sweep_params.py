from imc_trading.analysis.param_search import run_backtests
from imc_trading.config import LISTINGS, POSITION_LIMITS
from imc_trading.fair_value import calculate_amethysts_fair, calculate_starfruit_fair
from imc_trading.io.log_parser import _process_data_
from imc_trading.strategy.trader import PARAMS, Product, Trader


def main() -> None:
    market_data, trade_history = _process_data_("round_1_clean_data.log")
    trader = Trader()
    fair_calculations = {
        Product.AMETHYSTS: calculate_amethysts_fair,
        Product.STARFRUIT: calculate_starfruit_fair,
    }
    param_grid = {
        Product.AMETHYSTS: {
            "fair_value": [10000],
            "take_width": [1],
            "clear_width": [0.5],
            "volume_limit": [0],
            "disregard_edge": [2],
            "join_edge": [2],
            "default_edge": [4],
            "soft_position_limit": [10],
        },
        Product.STARFRUIT: {
            "take_width": [1],
            "clear_width": [-0.25, 0, 0.25],
            "prevent_adverse": [True],
            "adverse_volume": [15],
            "reversion_beta": [-0.229],
            "disregard_edge": [1],
            "join_edge": [0],
            "default_edge": [1],
        },
    }
    run_backtests(
        trader,
        LISTINGS,
        POSITION_LIMITS,
        fair_calculations,
        market_data,
        trade_history,
        "backtests",
        param_grid,
        Product.STARFRUIT,
    )


if __name__ == "__main__":
    main()
