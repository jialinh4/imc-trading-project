# Migration plan

## What was migrated without changing behavior
- `Backtester` notebook class -> `src/imc_trading/backtesting/legacy_backtester.py`
- `Trader`, `Product`, `PARAMS` -> `src/imc_trading/strategy/trader.py`
- `_process_data_` -> `src/imc_trading/io/log_parser.py`
- `calculate_starfruit_fair`, `calculate_amethysts_fair` -> `src/imc_trading/fair_value.py`
- `generate_param_combinations`, `run_backtests` -> `src/imc_trading/analysis/param_search.py`
- `analyze_log_files` -> `src/imc_trading/analysis/log_analysis.py`

## What was added for the target architecture
- `order_manager.py`
- `matching.py`
- `accounting.py`

These are intentionally introduced as clean modules first, before wiring them into the new backtester loop.

## Recommended migration order
1. Keep `legacy_backtester.py` runnable as a baseline.
2. Introduce a new `exchange_backtester.py` that uses `OrderManager`.
3. Replace `_execute_order` with `TakerMatcher`.
4. Add passive fills through `MakerMatcher`.
5. Replace legacy PnL dictionaries with `AccountingEngine`.
6. Add tests for order lifecycle, matching, and marking.


## Phase 4 status

- AccountingEngine now drives per-symbol and portfolio PnL snapshots.
- ExchangeBacktester activities log now includes realized / unrealized / total PnL columns.
- Queue-aware maker matching remains enabled from Phase 3.
- Next major step: adapt analysis scripts and submission workflow around the richer logs.
