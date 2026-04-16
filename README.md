# IMC Local Lab

A Python-first local IMC Prosperity workspace with two layers:

1. **Generic trader layer** for validating and replaying any official-style `Trader.py`
2. **Pepper research layer** for parameterized experiments, inventory studies, and grid search

This repository is designed to solve two different problems without mixing them together:

- **daily local development** of arbitrary competition traders
- **structured Pepper research** where the strategy must be parameterized and measurable

---

## Final status

This repository now supports all of the following:

### Generic trader workflows

- validate an official-style `Trader.py`
- backtest on IMC day CSV files
- replay against official submission-style `submission.json` / `submission.log`
- generate local artifacts:
  - `submission.log`
  - `activities.csv`
  - `sandbox_logs.json`
  - `trade_history.json`
  - `metrics.json`

### Pepper research workflows

- run one parameterized Pepper evaluation
- run three grid-search experiments:
  - **exp1**: opening floor × execution style
  - **exp2**: pullback threshold × add size × cooldown
  - **exp3**: one-level / two-level bid and ask overlay choices
- emit Pepper-specific metrics
- write per-run artifacts:
  - `pepper_summary.json`
  - `pepper_metrics.json`
  - `pepper_fills.json`
  - `pepper_inventory.csv`
- write experiment-level artifacts:
  - `expX_gridsearch.csv`
  - `expX_gridsearch.json`
  - `expX_summary.csv`
  - `expX_summary.json`
  - `expX_summary.md`
  - `expX_best_by_final_equity.json`
  - `expX_best_by_robust_score.json`

### Final optimization added in this version

Grid search now computes a **robustness layer** on top of raw `final_equity` ranking.

For each configuration, the repo re-runs the policy under several local execution assumptions and computes:

- `rank_base`
- `rank_conservative`
- `rank_strict`
- `robust_score = mean(rank across execution assumptions)`
- `rank_final_equity`
- `rank_robust_score`

This gives you two different answers after each experiment:

- **best by raw score**
- **best by stability / robustness**

---

## Why the Pepper engine is separate from the generic trader backtester

The Pepper requirements are reasonable, but they cannot be implemented cleanly by only replaying arbitrary black-box `Trader.py` files.

Several requested outputs require information that a generic replay cannot infer afterward:

- order intent labels such as `opening_floor`, `pullback_add`, `trim`, `hold_replenish`
- passive fill assumptions such as `opening_passive_fill_ratio`
- stateful cooldown logic for pullback adds
- sell classification needed for `unnecessary_sell_ratio`
- replenishment measurement needed for `replenishment_rate`

So the repository is intentionally split into:

- **generic trader layer**: replay any trader file that follows the official interface
- **Pepper policy layer**: run parameterized experiments where the engine explicitly knows the strategy structure

This split is necessary and is the correct design for your use case.

---

## Explicit limitations

- **Conversions are still recorded but not executed** in the generic local engine.
- Pepper passive fills are a **local backtest assumption**, not an official exchange model.
- `robust_score` is based on **local scenario definitions** in `src/imc_local_lab/pepper/gridsearch.py`, not on exchange-certified assumptions.

---

## Repository structure

```text
imc_local_lab/
├── README.md
├── pyproject.toml
├── requirements.txt
├── data/
│   ├── day_csv/
│   └── submissions/
├── examples/
│   ├── trader_official_example.py
│   ├── sample_trader.py
│   ├── pepper_submission.json
│   ├── day_csv/
│   │   ├── sample_prices.csv
│   │   ├── sample_trades.csv
│   │   └── sample_observations.csv
│   └── submissions/
│       └── sample_submission.json
├── runs/
├── scripts/
│   ├── example_commands.sh
│   └── run_tests.sh
├── src/
│   └── imc_local_lab/
│       ├── backtester.py
│       ├── cli.py
│       ├── datamodel.py
│       ├── dataset.py
│       ├── loaders.py
│       ├── trader_loader.py
│       └── pepper/
│           ├── gridsearch.py
│           ├── models.py
│           ├── policy.py
│           └── runner.py
├── tests/
└── traders/
```

---

## Core interfaces

### Generic trader interface

Any trader file loaded by the generic layer must expose:

```python
class Trader:
    def run(self, state: TradingState):
        return orders, conversions, traderData
```

The repo injects its own compatible `datamodel` module, so user files can keep:

```python
from datamodel import Order, OrderDepth, TradingState
```

### Pepper research interface

Pepper research does **not** use a hard-coded uploaded trader file directly.
It uses `PepperConfig` + `PepperPolicy`.

This is required so the engine can:

- vary parameters
- label order reasons
- simulate passive fills
- compute Pepper-only metrics correctly

---

## Metric definitions used in the Pepper engine

### Returns

- `final_equity = realized_pnl + unrealized_pnl`
- `realized_pnl`: cash PnL from executed fills
- `unrealized_pnl = final_position * final_mid_price`
- `markout_pnl`: fill-level markout against future mid over the configured horizon

### Inventory

- `avg_pos`
- `early_pos_5pct`
- `early_pos_10pct`
- `early_pos_20pct`
- `avg_pos_after_20pct`
- `avg_pos_after_50pct`
- `final_pos`
- `max_pos`
- `time_above_60`
- `time_above_70`

### Trend capture

Implemented as:

```text
capture_pnl = sum(position[t-1] * mid_diff[t])
ideal_long_capture_pnl = sum(position_limit * max(mid_diff[t], 0))
trend_capture_ratio = capture_pnl / ideal_long_capture_pnl
```

### Execution quality

- `avg_entry_price_first_10pct`
- `avg_entry_price_first_20pct`
- `avg_buy_price`
- `avg_pullback_add_price`
- `num_trades`
- `num_buy_trades`
- `num_sell_trades`
- `passive_fill_rate`
- `taker_fraction`

### Inventory maintenance

- `inventory_retention_rate = avg_pos_after_20pct / max(1, avg_pos_before_20pct)`
- `unnecessary_sell_ratio = non_trim_sell_volume / total_sell_volume`
- `replenishment_rate = replenishment_filled / replenishment_posted`

### Pullback extras

- `num_pullback_adds`
- `avg_pullback_depth_at_add`
- `post_add_return_20ticks`
- `post_add_return_50ticks`

---

## Execution assumptions used for `robust_score`

The current repository defines three local scenarios:

1. **base**
   - `passive_fill_ratio x 1.00`
   - `trade_match_mode = all`
2. **conservative**
   - `passive_fill_ratio x 0.75`
   - `trade_match_mode = all`
3. **strict**
   - `passive_fill_ratio x 0.50`
   - `trade_match_mode = worse`

Then:

```text
robust_score = mean(rank across scenarios)
```

Lower `robust_score` is better.

---

## Included runnable example files

These are included so you can test the repository immediately without needing your own dataset first.

### Generic trader example

- `examples/sample_trader.py`
- `examples/day_csv/sample_prices.csv`
- `examples/day_csv/sample_trades.csv`
- `examples/day_csv/sample_observations.csv`
- `examples/submissions/sample_submission.json`

### Pepper example

- `examples/pepper_submission.json`

Use these first to confirm your environment is correct.
Then replace them with your real datasets.

---

## Installation

### Option A: recommended editable install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

Then you can use the installed command:

```bash
imc-local --help
```

### Option B: no editable install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src
```

Then call with:

```bash
python -m imc_local_lab --help
```

In the rest of this README, both are equivalent.
If you did not run `pip install -e .`, prefix commands with `PYTHONPATH=src`.

---

## Quick smoke test: run the repository end-to-end

These commands are the fastest way to verify the repo is installed correctly.

### 1) Validate the included sample trader

```bash
imc-local validate-trader --trader examples/sample_trader.py
```

Expected output:

```json
{
  "status": "ok",
  "trader_class": "Trader"
}
```

### 2) Run a generic day-CSV backtest

```bash
imc-local backtest-day \
  --trader examples/sample_trader.py \
  --prices examples/day_csv/sample_prices.csv \
  --trades examples/day_csv/sample_trades.csv \
  --observations examples/day_csv/sample_observations.csv \
  --out runs/smoke_day
```

Expected artifacts:

```text
runs/smoke_day/
├── activities.csv
├── metrics.json
├── sandbox_logs.json
├── submission.log
└── trade_history.json
```

### 3) Run a generic submission replay

```bash
imc-local replay-submission \
  --trader examples/sample_trader.py \
  --submission examples/submissions/sample_submission.json \
  --out runs/smoke_submission
```

### 4) Run one Pepper evaluation

```bash
imc-local pepper-eval \
  --dataset examples/pepper_submission.json \
  --out runs/smoke_pepper_eval
```

Expected artifacts:

```text
runs/smoke_pepper_eval/
├── pepper_fills.json
├── pepper_inventory.csv
├── pepper_metrics.json
└── pepper_summary.json
```

### 5) Run Pepper experiment 1 grid search

```bash
imc-local pepper-gridsearch \
  --dataset examples/pepper_submission.json \
  --experiment exp1 \
  --out runs/smoke_pepper_exp1
```

Expected artifacts:

```text
runs/smoke_pepper_exp1/
├── exp1_gridsearch.csv
├── exp1_gridsearch.json
├── exp1_summary.csv
├── exp1_summary.json
├── exp1_summary.md
├── exp1_best_by_final_equity.json
├── exp1_best_by_robust_score.json
└── run_0000/
    ├── pepper_fills.json
    ├── pepper_inventory.csv
    ├── pepper_metrics.json
    └── pepper_summary.json
```

### 6) Run tests

```bash
pytest -q
```

---

## Detailed generic workflow

### Validate your own trader

Put your file at:

```text
traders/Trader.py
```

Then run:

```bash
imc-local validate-trader --trader traders/Trader.py
```

### Backtest your own trader on day CSV files

```bash
imc-local backtest-day \
  --trader traders/Trader.py \
  --prices data/day_csv/prices_round_1_day_-1.csv \
  --trades data/day_csv/trades_round_1_day_-1.csv \
  --observations data/day_csv/observations_round_1_day_-1.csv \
  --out runs/day_r1_d-1
```

### Replay your own trader against submission files

```bash
imc-local replay-submission \
  --trader traders/Trader.py \
  --submission data/submissions/60429.log \
  --out runs/replay_60429
```

If your file is JSON instead of LOG:

```bash
imc-local replay-submission \
  --trader traders/Trader.py \
  --submission data/submissions/60429.json \
  --out runs/replay_60429_json
```

### Use your uploaded Pepper-style trader file directly

If your file is not inside the repo yet:

```bash
imc-local validate-trader --trader /absolute/path/to/181919.py
```

Then backtest it the same way:

```bash
imc-local backtest-day \
  --trader /absolute/path/to/181919.py \
  --prices /absolute/path/to/prices_round_X_day_Y.csv \
  --trades /absolute/path/to/trades_round_X_day_Y.csv \
  --observations /absolute/path/to/observations_round_X_day_Y.csv \
  --out runs/ipr_local_test
```

---

## Detailed Pepper workflow

### Dataset requirement

Pepper commands default to:

```text
product = INTARIAN_PEPPER_ROOT
```

So the dataset passed to `pepper-eval` or `pepper-gridsearch` must actually contain `INTARIAN_PEPPER_ROOT`.

If you want a different product, pass:

```bash
--product YOUR_PRODUCT_NAME
```

### One-off Pepper evaluation

```bash
imc-local pepper-eval \
  --dataset examples/pepper_submission.json \
  --out runs/pepper_eval \
  --opening-floor-pos 60 \
  --opening-floor-progress 0.05 \
  --opening-style hybrid \
  --opening-taker-clip 10 \
  --opening-passive-clip 5 \
  --opening-passive-fill-ratio 0.25 \
  --main-target-pos 75 \
  --late-target-pos 75 \
  --pullback-window 20 \
  --pullback-threshold -2.0 \
  --pullback-add-size 10 \
  --pullback-cooldown-ticks 10 \
  --hold-band 5 \
  --bid-mode one_level \
  --bid-aggressiveness 1 \
  --ask-mode off \
  --ask-size-near-target 0 \
  --ask-size-above-target 2 \
  --tag manual
```

### Experiment 1

```bash
imc-local pepper-gridsearch \
  --dataset examples/pepper_submission.json \
  --experiment exp1 \
  --out runs/pepper_exp1
```

Grid:

- `opening_floor_pos = [40, 60, 70]`
- `opening_floor_progress = [0.03, 0.05]`
- `opening_style = ["taker", "passive", "hybrid"]`
- `opening_taker_clip = [10, 15]`
- `opening_passive_clip = [5, 10]`
- `opening_passive_fill_ratio = [0.25, 0.4]`

Fixed:

- `main_target_pos = 75`
- `late_target_pos = 75`
- `pullback_threshold = -2.0`
- `pullback_add_size = 10`
- `pullback_cooldown_ticks = 10`
- `bid_mode = one_level`
- `ask_mode = off`

Main output fields to inspect first:

- `final_equity`
- `early_pos_5pct`
- `early_pos_10pct`
- `avg_entry_price_first_10pct`
- `trend_capture_ratio`
- `robust_score`

### Experiment 2

First run experiment 1.
Then feed the best exp1 row into exp2:

```bash
imc-local pepper-gridsearch \
  --dataset examples/pepper_submission.json \
  --experiment exp2 \
  --best-exp1-json runs/pepper_exp1/exp1_gridsearch.json \
  --out runs/pepper_exp2
```

Grid:

- `pullback_window = [20, 50]`
- `pullback_threshold = [-1.0, -2.0, -3.0, -4.0]`
- `pullback_add_size = [5, 10, 15]`
- `pullback_cooldown_ticks = [5, 10, 20]`

Main outputs to inspect:

- `final_equity`
- `avg_pos`
- `avg_pullback_add_price`
- `num_pullback_adds`
- `trend_capture_ratio`
- `robust_score`

### Experiment 3

First run exp1 and exp2.
Then:

```bash
imc-local pepper-gridsearch \
  --dataset examples/pepper_submission.json \
  --experiment exp3 \
  --best-exp1-json runs/pepper_exp1/exp1_gridsearch.json \
  --best-exp2-json runs/pepper_exp2/exp2_gridsearch.json \
  --out runs/pepper_exp3
```

Grid:

- `hold_band = [3, 5]`
- `bid_mode = ["one_level", "two_level"]`
- `bid_aggressiveness = [1, 2]`
- `ask_mode = ["off", "tiny", "inventory_only"]`
- `ask_size_near_target = [0, 1, 2]`
- `ask_size_above_target = [2, 5]`

Main outputs to inspect:

- `final_equity`
- `inventory_retention_rate`
- `unnecessary_sell_ratio`
- `avg_pos_after_20pct`
- `avg_pos_after_50pct`
- `replenishment_rate`
- `robust_score`

---

## How to read the experiment outputs

### `expX_gridsearch.csv` / `expX_gridsearch.json`

These are the raw base-assumption runs, sorted by `final_equity` descending.

Use these to answer:

- which configuration wins under the default local assumption?

### `expX_summary.csv` / `expX_summary.json`

These augment each configuration with:

- `final_equity_base`
- `final_equity_conservative`
- `final_equity_strict`
- `rank_base`
- `rank_conservative`
- `rank_strict`
- `robust_score`
- `rank_final_equity`
- `rank_robust_score`

Use these to answer:

- which configuration stays good when execution assumptions get worse?

### `expX_summary.md`

Human-readable summary containing:

- best by `final_equity`
- best by `robust_score`
- top-k robust rows in table form

### `expX_best_by_final_equity.json`

The single best configuration under the base assumption.

### `expX_best_by_robust_score.json`

The single most stable configuration under the current local scenario set.

---

## Recommended decision rule after each experiment

### After exp1

Do **not** select only by highest `final_equity`.
Compare:

- `final_equity`
- `early_pos_5pct`
- `early_pos_10pct`
- `avg_entry_price_first_10pct`
- `trend_capture_ratio`
- `robust_score`

Typical interpretation:

- if a config wins only in raw PnL but ranks poorly in robustness, it may be overfit to the base assumption
- if a config has slightly lower PnL but much better `robust_score`, it is usually safer to carry forward

### After exp2

Compare:

- `final_equity`
- `num_pullback_adds`
- `avg_pullback_add_price`
- `avg_pullback_depth_at_add`
- `post_add_return_20ticks`
- `post_add_return_50ticks`
- `robust_score`

### After exp3

Compare:

- `final_equity`
- `inventory_retention_rate`
- `unnecessary_sell_ratio`
- `avg_pos_after_20pct`
- `avg_pos_after_50pct`
- `replenishment_rate`
- `robust_score`

---

## Exact commands that were used to verify this repository

These commands were run successfully in the build environment:

```bash
pytest -q

PYTHONPATH=src python -m imc_local_lab validate-trader \
  --trader examples/sample_trader.py

PYTHONPATH=src python -m imc_local_lab backtest-day \
  --trader examples/sample_trader.py \
  --prices examples/day_csv/sample_prices.csv \
  --trades examples/day_csv/sample_trades.csv \
  --observations examples/day_csv/sample_observations.csv \
  --out /tmp/imc_run_day

PYTHONPATH=src python -m imc_local_lab replay-submission \
  --trader examples/sample_trader.py \
  --submission examples/submissions/sample_submission.json \
  --out /tmp/imc_run_submission

PYTHONPATH=src python -m imc_local_lab pepper-eval \
  --dataset examples/pepper_submission.json \
  --out /tmp/imc_pepper

PYTHONPATH=src python -m imc_local_lab pepper-gridsearch \
  --dataset examples/pepper_submission.json \
  --experiment exp1 \
  --out /tmp/imc_pepper_grid
```

---

## Troubleshooting

### `No module named datamodel`

Use the repository loader instead of running your trader file directly.
Correct:

```bash
imc-local validate-trader --trader traders/Trader.py
```

### `product INTARIAN_PEPPER_ROOT was not found in dataset ...`

Your Pepper dataset does not contain the default Pepper product.
Either:

- use a dataset that includes `INTARIAN_PEPPER_ROOT`
- or pass `--product YOUR_PRODUCT`

### `imc-local: command not found`

You probably skipped editable install.
Use either:

```bash
pip install -e .
```

or:

```bash
export PYTHONPATH=src
python -m imc_local_lab --help
```

### `pepper-gridsearch` is slow

That is expected for large grids.
Each row is a full local run.
Use smaller grids first if you want quick iteration.

---

## Convenience scripts

### Example commands

```bash
bash scripts/example_commands.sh
```

### Run tests

```bash
bash scripts/run_tests.sh
```

---

## Suggested next step for your project

Use this repo in two modes:

1. keep your real submitted or experimental `Trader.py` files in `traders/` and use the **generic layer** for replay/backtest
2. use the **Pepper layer** to search for:
   - best opening floor rule
   - best pullback add rule
   - best bid/ask overlay rule

Then translate the chosen Pepper configuration back into your production trader logic.
