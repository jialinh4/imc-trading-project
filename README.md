# IMC Trading Project

Python codebase for IMC Prosperity development, backtesting, log analysis, and round-by-round submission management.

This repository started as a migration from `backtester-refined.ipynb` into a maintainable Python package. The original notebook is preserved under `archive/` so the migration can be audited line by line.

## Repository goals

- Develop trading strategies in Python modules instead of a monolithic notebook
- Preserve the current notebook-equivalent backtester as a baseline
- Introduce a cleaner execution architecture for order lifecycle, matching, and accounting
- Support the full workflow: development -> testing -> backtesting -> review -> parameter tuning -> submission packaging

## Current status

- `legacy_backtester.py` is the current runnable baseline migrated from the notebook
- Strategy logic lives in `src/imc_trading/strategy/trader.py`
- New architecture scaffolding exists for order management, matching, and accounting
- The new execution flow is **not yet** fully wired into the main backtest loop

## Project layout

```text
.
├── archive/                    # Original notebook and exported cell snapshots
├── data/
│   ├── raw/                    # Raw market / trade files kept locally
│   └── processed/              # Processed data artifacts kept locally
├── logs/                       # Generated backtest logs
├── notebooks/                  # Research and visualization notebooks only
├── outputs/                    # Analysis outputs, plots, reports
├── scripts/                    # CLI-style entry points
├── src/imc_trading/
│   ├── analysis/               # Parameter sweeps and log analysis
│   ├── backtesting/            # Backtest engines and execution modules
│   ├── io/                     # Parsing and I/O helpers
│   ├── strategy/               # Strategy implementation
│   ├── config.py               # Shared constants / config helpers
│   └── fair_value.py           # Fair value utilities
├── submissions/                # Final per-round submission snapshots
└── tests/                      # Automated tests
```

## Module responsibilities

### `src/imc_trading/strategy/`
Trading logic only.

- fair value estimation
- take / clear / make decisions
- round-specific strategy evolution

### `src/imc_trading/backtesting/`
Simulation and execution logic.

- `legacy_backtester.py`: migrated notebook baseline
- `order_manager.py`: order lifecycle state
- `matching.py`: taker / maker matching components
- `accounting.py`: realized / unrealized PnL tracking

### `src/imc_trading/analysis/`
Offline analysis and parameter experiments.

- batch parameter sweeps
- parsing experiment outputs
- comparing log files and runs

### `scripts/`
Operational entry points.

- run one backtest
- run parameter sweeps
- analyze saved logs

### `archive/`
Migration safety net. These files should not be edited unless you are checking notebook-to-package equivalence.

## Recommended development workflow

### Core rule
Use `.py` files for production logic and `.ipynb` only for exploration, plots, and review.

### Suggested loop
1. Implement or modify logic under `src/`
2. Add or update tests under `tests/`
3. Run a fixed backtest from `scripts/`
4. Save logs to `logs/`
5. Analyze results with notebooks or analysis scripts
6. Freeze a clean submission snapshot under `submissions/`

## Setup

### 1. Create an environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### 2. Provide IMC datamodel

The migrated code expects the official IMC `datamodel.py` to be importable.

Recommended options:
- place `datamodel.py` at the repository root for local development, or
- install / expose it on the Python path in your environment

`datamodel.py` is ignored by git because it may differ between rounds or come from official starter files.

### 3. Verify the package layout

```bash
pytest
```

## Git repository setup

If this folder is not yet a git repository:

```bash
git init
git branch -M main
git add .
git commit -m "Initialize IMC trading project scaffold"
```

Recommended next steps:

```bash
git checkout -b feature/exchange-backtester
```

## Branching suggestion

- `main`: stable, runnable baseline
- `feature/exchange-backtester`: new execution architecture
- `feature/round-x-strategy`: round-specific strategy work
- `experiment/*`: short-lived research branches

## Submission convention

Store final round submissions under `submissions/`, for example:

```text
submissions/
├── round1/
│   ├── trader_submission.py
│   └── notes.md
├── round2/
│   ├── trader_submission.py
│   └── notes.md
```

This keeps the main strategy code separate from the exact file sent to the competition platform.

## Immediate next implementation targets

1. Add `exchange_backtester.py`
2. Wire `OrderManager.submit_order()` into the event loop
3. Separate taker and maker execution paths
4. Preserve resting orders across timestamps
5. Replace legacy PnL marking with `AccountingEngine`
6. Expand tests beyond layout validation


## Phase 4 status

- AccountingEngine now drives per-symbol and portfolio PnL snapshots.
- ExchangeBacktester activities log now includes realized / unrealized / total PnL columns.
- Queue-aware maker matching remains enabled from Phase 3.
- Next major step: adapt analysis scripts and submission workflow around the richer logs.
