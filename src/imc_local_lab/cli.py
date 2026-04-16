from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from .backtester import Backtester
from .batch import run_selections
from .loaders import load_day_dataset, load_submission_dataset
from .pepper import PepperConfig, PepperExperimentRunner, grid_for_experiment, run_gridsearch
from .resolver import (
    auto_pick_trader,
    default_datasets_root,
    default_trader_roots,
    parse_limit_overrides,
    resolve_selections,
)
from .trader_loader import TraderLoadError, load_trader_instance


PACKAGE_ROOT = Path(__file__).resolve().parent


def cmd_validate(args: argparse.Namespace) -> int:
    trader = load_trader_instance(Path(args.trader))
    print(json.dumps({"status": "ok", "trader_class": trader.__class__.__name__}, indent=2))
    return 0


def cmd_backtest_day(args: argparse.Namespace) -> int:
    trader = load_trader_instance(Path(args.trader))
    dataset = load_day_dataset(
        prices_csv=Path(args.prices),
        trades_csv=Path(args.trades) if args.trades else None,
        observations_csv=Path(args.observations) if args.observations else None,
        dataset_id=args.dataset_id,
    )
    summary = Backtester(dataset=dataset, position_limits=parse_limit_overrides(args.limit), trade_match_mode=args.trade_match_mode).run(
        trader=trader,
        out_dir=Path(args.out),
    )
    print(json.dumps(_summary_dict(summary), indent=2))
    return 0


def cmd_replay_submission(args: argparse.Namespace) -> int:
    trader = load_trader_instance(Path(args.trader))
    dataset = load_submission_dataset(Path(args.submission), dataset_id=args.dataset_id)
    summary = Backtester(dataset=dataset, position_limits=parse_limit_overrides(args.limit), trade_match_mode=args.trade_match_mode).run(
        trader=trader,
        out_dir=Path(args.out),
    )
    print(json.dumps(_summary_dict(summary), indent=2))
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    trader_path = Path(args.algorithm) if args.algorithm else auto_pick_trader(default_trader_roots(PACKAGE_ROOT))
    datasets_root = Path(args.data) if args.data else default_datasets_root(PACKAGE_ROOT)
    selections = resolve_selections(datasets_root, args.days, include_submission=args.include_submission)
    result = run_selections(
        selections=selections,
        trader_path=trader_path,
        out_dir=Path(args.out),
        trade_match_mode=args.trade_match_mode,
        position_limits=parse_limit_overrides(args.limit),
        carry_state=args.carry,
    )
    payload = {
        'mode': result.mode,
        'summary_json': str(result.summary_path),
        'summary_md': str(result.markdown_path),
        'runs': result.outputs,
    }
    print(json.dumps(payload, indent=2))
    return 0


def cmd_pepper_eval(args: argparse.Namespace) -> int:
    dataset = _load_dataset_from_args(args)
    config = _pepper_config_from_args(args)
    result = PepperExperimentRunner(dataset, config).run(out_dir=Path(args.out))
    print(json.dumps({"config": config.to_dict(), "metrics": result.metrics}, indent=2))
    return 0


def cmd_pepper_gridsearch(args: argparse.Namespace) -> int:
    dataset = _load_dataset_from_args(args)
    best_exp1 = _load_best_row(Path(args.best_exp1_json)) if args.best_exp1_json else None
    best_exp2 = _load_best_row(Path(args.best_exp2_json)) if args.best_exp2_json else None
    configs = grid_for_experiment(args.experiment, best_exp1=best_exp1, best_exp2=best_exp2)
    result = run_gridsearch(dataset, args.experiment, configs, Path(args.out))
    payload = {
        "experiment": result.experiment,
        "num_runs": len(result.rows),
        "grid_csv": str(result.csv_path) if result.csv_path else None,
        "grid_json": str(result.json_path) if result.json_path else None,
        "summary_csv": str(result.summary_csv_path) if result.summary_csv_path else None,
        "summary_json": str(result.summary_json_path) if result.summary_json_path else None,
        "summary_md": str(result.markdown_summary_path) if result.markdown_summary_path else None,
        "best_by_final_equity": str(result.best_final_path) if result.best_final_path else None,
        "best_by_robust_score": str(result.best_robust_path) if result.best_robust_path else None,
        "best": result.rows[0] if result.rows else None,
    }
    print(json.dumps(payload, indent=2))
    return 0


def _load_dataset_from_args(args: argparse.Namespace):
    dataset_path = Path(args.dataset)
    if dataset_path.suffix.lower() == '.csv':
        return load_day_dataset(
            prices_csv=dataset_path,
            trades_csv=Path(args.trades) if getattr(args, 'trades', None) else None,
            observations_csv=Path(args.observations) if getattr(args, 'observations', None) else None,
            dataset_id=args.dataset_id,
        )
    return load_submission_dataset(dataset_path, dataset_id=args.dataset_id)


def _load_best_row(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(payload, list):
        if not payload:
            raise ValueError(f'best-row source is empty: {path}')
        return dict(payload[0])
    if isinstance(payload, dict):
        return dict(payload)
    raise ValueError(f'unsupported best-row payload: {path}')


def _pepper_config_from_args(args: argparse.Namespace) -> PepperConfig:
    kwargs: Dict[str, Any] = {
        'product': args.product,
        'opening_floor_pos': args.opening_floor_pos,
        'opening_floor_progress': args.opening_floor_progress,
        'opening_style': args.opening_style,
        'opening_taker_clip': args.opening_taker_clip,
        'opening_passive_clip': args.opening_passive_clip,
        'opening_passive_fill_ratio': args.opening_passive_fill_ratio,
        'passive_fill_ratio': args.opening_passive_fill_ratio,
        'main_target_pos': args.main_target_pos,
        'late_target_pos': args.late_target_pos,
        'pullback_window': args.pullback_window,
        'pullback_threshold': args.pullback_threshold,
        'pullback_add_size': args.pullback_add_size,
        'pullback_cooldown_ticks': args.pullback_cooldown_ticks,
        'hold_band': args.hold_band,
        'bid_mode': args.bid_mode,
        'bid_aggressiveness': args.bid_aggressiveness,
        'ask_mode': args.ask_mode,
        'ask_size_near_target': args.ask_size_near_target,
        'ask_size_above_target': args.ask_size_above_target,
        'tag': args.tag,
    }
    return PepperConfig(**kwargs)


def _summary_dict(summary) -> dict:
    return {
        'dataset_id': summary.dataset_id,
        'tick_count': summary.tick_count,
        'final_pnl_total': summary.final_pnl_total,
        'final_pnl_by_product': summary.final_pnl_by_product,
        'artifacts': {
            'metrics': str(summary.artifacts.metrics_path),
            'submission_log': str(summary.artifacts.submission_log_path),
            'activities_csv': str(summary.artifacts.activities_csv_path),
            'sandbox_logs': str(summary.artifacts.sandbox_logs_path),
            'trade_history': str(summary.artifacts.trade_history_path),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='imc-prosperity', description='Merged local IMC Prosperity backtester')
    subparsers = parser.add_subparsers(dest='command', required=True)

    validate = subparsers.add_parser('validate-trader', help='Load a Trader file and validate the class import')
    validate.add_argument('--trader', required=True)
    validate.set_defaults(func=cmd_validate)

    day = subparsers.add_parser('backtest-day', help='Backtest a Trader on one prices/trades CSV set')
    day.add_argument('--trader', required=True)
    day.add_argument('--prices', required=True)
    day.add_argument('--trades')
    day.add_argument('--observations')
    day.add_argument('--dataset-id')
    day.add_argument('--trade-match-mode', choices=['all', 'worse', 'none'], default='all')
    day.add_argument('--limit', action='append', default=[], help='Override product limit as PRODUCT:LIMIT')
    day.add_argument('--out', required=True)
    day.set_defaults(func=cmd_backtest_day)

    replay = subparsers.add_parser('replay-submission', help='Replay a Trader on one submission .json/.log file')
    replay.add_argument('--trader', required=True)
    replay.add_argument('--submission', required=True)
    replay.add_argument('--dataset-id')
    replay.add_argument('--trade-match-mode', choices=['all', 'worse', 'none'], default='all')
    replay.add_argument('--limit', action='append', default=[], help='Override product limit as PRODUCT:LIMIT')
    replay.add_argument('--out', required=True)
    replay.set_defaults(func=cmd_replay_submission)

    merged = subparsers.add_parser('backtest', help='Round/day style batch backtest inspired by the open-source tools')
    merged.add_argument('algorithm', nargs='?', help='Path to Trader.py; omitted means auto-pick latest local trader')
    merged.add_argument('days', nargs='*', help='Examples: 0, 1, 1-0, 1--1, 1-submission')
    merged.add_argument('--data', help='Dataset root directory (defaults to ./datasets)')
    merged.add_argument('--out', required=True, help='Output directory for all run artifacts')
    merged.add_argument('--trade-match-mode', choices=['all', 'worse', 'none'], default='all')
    merged.add_argument('--limit', action='append', default=[], help='Override product limit as PRODUCT:LIMIT')
    merged.add_argument('--carry', action='store_true', help='Carry trader state, position, and pnl across selected days')
    merged.add_argument('--include-submission', action='store_true', help='Also run submission.json/log when present in a selected round directory')
    merged.set_defaults(func=cmd_backtest)

    pepper_eval = subparsers.add_parser('pepper-eval', help='Run one parameterized Pepper experiment')
    pepper_eval.add_argument('--dataset', required=True)
    pepper_eval.add_argument('--dataset-id')
    pepper_eval.add_argument('--trades')
    pepper_eval.add_argument('--observations')
    pepper_eval.add_argument('--out', required=True)
    pepper_eval.add_argument('--product', default='INTARIAN_PEPPER_ROOT')
    pepper_eval.add_argument('--opening-floor-pos', type=int, default=60)
    pepper_eval.add_argument('--opening-floor-progress', type=float, default=0.05)
    pepper_eval.add_argument('--opening-style', choices=['taker', 'passive', 'hybrid'], default='taker')
    pepper_eval.add_argument('--opening-taker-clip', type=int, default=10)
    pepper_eval.add_argument('--opening-passive-clip', type=int, default=5)
    pepper_eval.add_argument('--opening-passive-fill-ratio', type=float, default=0.25)
    pepper_eval.add_argument('--main-target-pos', type=int, default=75)
    pepper_eval.add_argument('--late-target-pos', type=int, default=75)
    pepper_eval.add_argument('--pullback-window', type=int, default=20)
    pepper_eval.add_argument('--pullback-threshold', type=float, default=-2.0)
    pepper_eval.add_argument('--pullback-add-size', type=int, default=10)
    pepper_eval.add_argument('--pullback-cooldown-ticks', type=int, default=10)
    pepper_eval.add_argument('--hold-band', type=int, default=5)
    pepper_eval.add_argument('--bid-mode', choices=['one_level', 'two_level'], default='one_level')
    pepper_eval.add_argument('--bid-aggressiveness', type=int, default=1)
    pepper_eval.add_argument('--ask-mode', choices=['off', 'tiny', 'inventory_only'], default='off')
    pepper_eval.add_argument('--ask-size-near-target', type=int, default=0)
    pepper_eval.add_argument('--ask-size-above-target', type=int, default=2)
    pepper_eval.add_argument('--tag', default='manual')
    pepper_eval.set_defaults(func=cmd_pepper_eval)

    pepper_grid = subparsers.add_parser('pepper-gridsearch', help='Run Pepper experiment grids (exp1/exp2/exp3)')
    pepper_grid.add_argument('--dataset', required=True)
    pepper_grid.add_argument('--dataset-id')
    pepper_grid.add_argument('--trades')
    pepper_grid.add_argument('--observations')
    pepper_grid.add_argument('--experiment', choices=['exp1', 'exp2', 'exp3'], required=True)
    pepper_grid.add_argument('--best-exp1-json')
    pepper_grid.add_argument('--best-exp2-json')
    pepper_grid.add_argument('--out', required=True)
    pepper_grid.set_defaults(func=cmd_pepper_gridsearch)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except TraderLoadError as exc:
        parser.error(str(exc))
        return 2
    except Exception as exc:
        parser.error(str(exc))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
