#!/usr/bin/env bash
set -euo pipefail

# Use this if you did not install with `pip install -e .`
export PYTHONPATH=src

# 1) Validate a trader file
python -m imc_local_lab validate-trader --trader examples/sample_trader.py

# 2) Backtest a generic trader on day CSV files
python -m imc_local_lab backtest-day \
  --trader examples/sample_trader.py \
  --prices examples/day_csv/sample_prices.csv \
  --trades examples/day_csv/sample_trades.csv \
  --observations examples/day_csv/sample_observations.csv \
  --out runs/smoke_day

# 3) Replay a generic trader on an official submission-style JSON file
python -m imc_local_lab replay-submission \
  --trader examples/sample_trader.py \
  --submission examples/submissions/sample_submission.json \
  --out runs/smoke_submission

# 4) Run one Pepper experiment
python -m imc_local_lab pepper-eval \
  --dataset examples/pepper_submission.json \
  --out runs/smoke_pepper_eval \
  --opening-floor-pos 60 \
  --opening-floor-progress 0.05 \
  --opening-style hybrid \
  --opening-taker-clip 10 \
  --opening-passive-clip 5 \
  --opening-passive-fill-ratio 0.25 \
  --pullback-window 20 \
  --pullback-threshold -2.0 \
  --pullback-add-size 10 \
  --pullback-cooldown-ticks 10 \
  --bid-mode one_level \
  --ask-mode off

# 5) Pepper grid search: experiment 1
python -m imc_local_lab pepper-gridsearch \
  --dataset examples/pepper_submission.json \
  --experiment exp1 \
  --out runs/pepper_exp1

# 6) Pepper grid search: experiment 2 (requires best exp1 file)
python -m imc_local_lab pepper-gridsearch \
  --dataset examples/pepper_submission.json \
  --experiment exp2 \
  --best-exp1-json runs/pepper_exp1/exp1_gridsearch.json \
  --out runs/pepper_exp2

# 7) Pepper grid search: experiment 3 (requires best exp1 + exp2 files)
python -m imc_local_lab pepper-gridsearch \
  --dataset examples/pepper_submission.json \
  --experiment exp3 \
  --best-exp1-json runs/pepper_exp1/exp1_gridsearch.json \
  --best-exp2-json runs/pepper_exp2/exp2_gridsearch.json \
  --out runs/pepper_exp3

# 8) Run tests
pytest -q
