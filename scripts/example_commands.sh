#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

python -m imc_local_lab validate-trader --trader examples/sample_trader.py

python -m imc_local_lab backtest-day   --trader examples/sample_trader.py   --prices examples/day_csv/sample_prices.csv   --trades examples/day_csv/sample_trades.csv   --observations examples/day_csv/sample_observations.csv   --out runs/smoke_day

python -m imc_local_lab replay-submission   --trader examples/sample_trader.py   --submission examples/submissions/sample_submission.json   --out runs/smoke_submission

python -m imc_local_lab backtest   examples/sample_trader.py 0 0-submission   --data datasets   --out runs/smoke_batch

python -m imc_local_lab backtest   examples/sample_trader.py 0   --data datasets   --carry   --out runs/smoke_batch_carry

python -m imc_local_lab pepper-eval   --dataset examples/pepper_submission.json   --out runs/smoke_pepper_eval   --product INTARIAN_PEPPER_ROOT   --opening-floor-pos 60   --opening-floor-progress 0.05   --opening-style taker   --opening-taker-clip 10   --opening-passive-clip 5   --opening-passive-fill-ratio 0.25   --main-target-pos 75   --late-target-pos 75   --pullback-window 20   --pullback-threshold -2.0   --pullback-add-size 10   --pullback-cooldown-ticks 10   --bid-mode one_level   --ask-mode off

python -m imc_local_lab pepper-gridsearch   --dataset examples/pepper_submission.json   --experiment exp1   --out runs/pepper_exp1

python -m imc_local_lab pepper-gridsearch   --dataset examples/pepper_submission.json   --experiment exp2   --best-exp1-json runs/pepper_exp1/exp1_best_by_robust_score.json   --out runs/pepper_exp2

python -m imc_local_lab pepper-gridsearch   --dataset examples/pepper_submission.json   --experiment exp3   --best-exp1-json runs/pepper_exp1/exp1_best_by_robust_score.json   --best-exp2-json runs/pepper_exp2/exp2_best_by_robust_score.json   --out runs/pepper_exp3
