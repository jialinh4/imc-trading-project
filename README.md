# IMC Prosperity Merged Local Backtester

This repository is a **single local codebase** built to cover the gap between:

- the **self-contained round-folder workflow** of `GeyzsoN/prosperity_rust_backtester`
- the **algorithm file + round/day CLI workflow** of `t-hersch/imc-prosperity-4-backtester`

and to keep the additional **Pepper experiment / grid search** workflow that was developed during this project.

## What this repo does

It supports three layers of usage:

1. **Single dataset backtests**
   - run on one `prices_*.csv` / `trades_*.csv` / `observations_*.csv`
   - replay on one `submission.json` or `submission.log`

2. **Round/day batch backtests**
   - select rounds and days with selectors like:
     - `0`
     - `1`
     - `1-0`
     - `1--1`
     - `1-submission`
   - run independent day backtests or carry state across selected days

3. **Pepper experiment layer**
   - parameterized Pepper evaluation
   - grid search for `exp1`, `exp2`, `exp3`
   - robust-score summary output

## Main design choices

This codebase is **Python-first**.

It does **not** embed the Rust toolchain from the Rust repo. Instead, it takes the best parts of the two open-source repos and merges them into a single local Python project:

- round-folder dataset discovery
- day selector CLI
- submission replay support
- official-style `datamodel` injection for arbitrary `Trader.py`
- order matching modes: `all`, `worse`, `none`
- per-product position limits with CLI override
- official-style `submission.log` artifact generation

## Important current limitation

`conversions` are **recorded from `Trader.run` output but are not executed** in this engine.

This means the repository is suitable for the current local development workflow when your trader logic is based on standard order placement, but if a future round depends materially on conversion execution, that part still needs to be added.

## Repository layout

```text
.
├── datasets/
│   ├── tutorial/
│   ├── round1/
│   ├── round2/
│   ├── round3/
│   ├── round4/
│   ├── round5/
│   ├── round6/
│   ├── round7/
│   └── round8/
├── examples/
├── runs/
├── scripts/
├── src/imc_local_lab/
│   ├── backtester.py
│   ├── batch.py
│   ├── cli.py
│   ├── datamodel.py
│   ├── dataset.py
│   ├── loaders.py
│   ├── resolver.py
│   ├── trader_loader.py
│   └── pepper/
├── tests/
└── traders/
```

## Installation

### Standard venv setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e . --no-build-isolation
```

### Run tests

```bash
pytest -q
```

## Commands

After installation, you can use either:

```bash
imc-prosperity
```

or:

```bash
python -m imc_local_lab
```

### 1. Validate a trader

```bash
imc-prosperity validate-trader --trader path/to/Trader.py
```

### 2. Backtest one day CSV dataset

```bash
imc-prosperity backtest-day   --trader path/to/Trader.py   --prices path/to/prices_round_1_day_0.csv   --trades path/to/trades_round_1_day_0.csv   --observations path/to/observations_round_1_day_0.csv   --out runs/day_single
```

### 3. Replay one submission log/json

```bash
imc-prosperity replay-submission   --trader path/to/Trader.py   --submission path/to/submission.json   --out runs/submission_single
```

### 4. Batch backtest by round/day selectors

Examples:

```bash
imc-prosperity backtest examples/sample_trader.py 0 --data datasets --out runs/tutorial_all
imc-prosperity backtest examples/sample_trader.py 0-submission --data datasets --out runs/tutorial_submission
imc-prosperity backtest examples/sample_trader.py 1 1--1 1-0 --data datasets --out runs/round_mix
```

Selector meanings:

- `0` = tutorial round
- `1` = all available day CSV files in `datasets/round1`
- `1-0` = round 1 day 0
- `1--1` = round 1 day -1
- `1-submission` = `submission.json` or `submission.log` inside `datasets/round1`

### 5. Carry trader state across selected days

```bash
imc-prosperity backtest examples/sample_trader.py 0 --data datasets --carry --out runs/tutorial_carry
```

This builds one merged dataset in day order and runs the backtest through it continuously.

### 6. Override position limits

```bash
imc-prosperity backtest examples/sample_trader.py 0   --data datasets   --limit EMERALDS:80   --limit TOMATOES:80   --out runs/tutorial_limits
```

### 7. Pepper evaluation and grid search

```bash
imc-prosperity pepper-eval   --dataset examples/pepper_submission.json   --out runs/pepper_eval
```

```bash
imc-prosperity pepper-gridsearch   --dataset examples/pepper_submission.json   --experiment exp1   --out runs/pepper_exp1
```

```bash
imc-prosperity pepper-gridsearch   --dataset examples/pepper_submission.json   --experiment exp2   --best-exp1-json runs/pepper_exp1/exp1_best_by_robust_score.json   --out runs/pepper_exp2
```

```bash
imc-prosperity pepper-gridsearch   --dataset examples/pepper_submission.json   --experiment exp3   --best-exp1-json runs/pepper_exp1/exp1_best_by_robust_score.json   --best-exp2-json runs/pepper_exp2/exp2_best_by_robust_score.json   --out runs/pepper_exp3
```

## Generated artifacts

### Single-run backtests

Each single run writes:

- `metrics.json`
- `submission.log`
- `activities.csv`
- `sandbox_logs.json`
- `trade_history.json`

### Batch backtests

Each batch run writes:

- one subdirectory per selected dataset, or one `carry_merged/` directory in carry mode
- `batch_summary.json`
- `batch_summary.md`

### Pepper grid search

Each Pepper grid search writes:

- `expX_gridsearch.csv`
- `expX_gridsearch.json`
- `expX_summary.csv`
- `expX_summary.json`
- `expX_summary.md`
- `expX_best_by_final_equity.json`
- `expX_best_by_robust_score.json`

## Quick smoke test

```bash
bash scripts/example_commands.sh
```

This runs:

- trader validation
- day CSV backtest
- submission replay
- tutorial round batch run
- tutorial carry run
- Pepper eval
- Pepper exp1 / exp2 / exp3

## Makefile shortcuts

```bash
make test
make tutorial
make tutorial DAY=-1
make round ROUND=1
make round ROUND=1 DAY=0
make submission ROUND=0
```

## What to put where

### Put your real trader here

Recommended:

```text
traders/Trader.py
```

Then run:

```bash
imc-prosperity backtest traders/Trader.py 0 --data datasets --out runs/my_run
```

### Put IMC datasets here

- tutorial data in `datasets/tutorial/`
- round 1 data in `datasets/round1/`
- round 2 data in `datasets/round2/`
- etc.

Expected naming:

```text
prices_round_<round>_day_<day>.csv
trades_round_<round>_day_<day>.csv
observations_round_<round>_day_<day>.csv
submission.json
submission.log
```

## Notes on intent

This repository is not a literal line-by-line source merge of the two open-source projects.

It is a **single consolidated local implementation** that merges the parts that matter for the current competition workflow:

- `GeyzsoN`-style round folders and local artifacts
- `t-hersch`-style day selector workflow and Python datamodel compatibility
- the Pepper evaluation tooling developed in this project

That keeps the codebase smaller, easier to run locally, and easier to modify than trying to vendor both repositories wholesale.
