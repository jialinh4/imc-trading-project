import itertools
import os
from tqdm import tqdm

from imc_trading.backtesting.legacy_backtester import Backtester



def generate_param_combinations(param_grid):
    param_names = param_grid.keys()
    param_values = param_grid.values()
    combinations = list(itertools.product(*param_values))
    return [dict(zip(param_names, combination)) for combination in combinations]


def run_backtests(trader, listings, position_limit, fair_calcs, market_data, trade_history, backtest_dir, param_grid, symbol):
    if not os.path.exists(backtest_dir):
        os.makedirs(backtest_dir)

    param_combinations = generate_param_combinations(param_grid[symbol])

    results = []
    for params in tqdm(param_combinations, desc=f"Running backtests for {symbol}", unit="backtest"):
        trader.params = {symbol: params}
        backtester = Backtester(trader, listings, position_limit, fair_calcs, market_data, trade_history)
        backtester.run()

        param_str = "-".join([f"{key}={value}" for key, value in params.items()])
        log_filename = f"{backtest_dir}/{symbol}_{param_str}.log"
        backtester._log_trades(log_filename)

        results.append((params, backtester.pnl[symbol]))

    return results
