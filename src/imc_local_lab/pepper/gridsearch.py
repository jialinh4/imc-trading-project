from __future__ import annotations

import csv
import itertools
import json
from dataclasses import replace
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from ..dataset import NormalizedDataset
from .models import GridSearchResult, PepperConfig
from .runner import PepperExperimentRunner

# Execution assumptions used to compute a simple robustness score.
# These are local backtest assumptions, not official exchange rules.
ROBUSTNESS_SCENARIOS: Tuple[Tuple[str, float, str], ...] = (
    ("base", 1.00, "all"),
    ("conservative", 0.75, "all"),
    ("strict", 0.50, "worse"),
)


def grid_for_experiment(
    experiment: str,
    best_exp1: Dict[str, object] | None = None,
    best_exp2: Dict[str, object] | None = None,
) -> List[PepperConfig]:
    experiment = experiment.lower()
    if experiment == "exp1":
        opening_floor_pos = [40, 60, 70]
        opening_floor_progress = [0.03, 0.05]
        opening_style = ["taker", "passive", "hybrid"]
        opening_taker_clip = [10, 15]
        opening_passive_clip = [5, 10]
        opening_passive_fill_ratio = [0.25, 0.4]
        configs: List[PepperConfig] = []
        for floor_pos, floor_progress, style, taker_clip, passive_clip, passive_ratio in itertools.product(
            opening_floor_pos,
            opening_floor_progress,
            opening_style,
            opening_taker_clip,
            opening_passive_clip,
            opening_passive_fill_ratio,
        ):
            configs.append(
                PepperConfig(
                    opening_floor_pos=floor_pos,
                    opening_floor_progress=floor_progress,
                    opening_style=style,
                    opening_taker_clip=taker_clip,
                    opening_passive_clip=passive_clip,
                    opening_passive_fill_ratio=passive_ratio,
                    passive_fill_ratio=passive_ratio,
                    main_target_pos=75,
                    late_target_pos=75,
                    pullback_threshold=-2.0,
                    pullback_add_size=10,
                    pullback_cooldown_ticks=10,
                    bid_mode="one_level",
                    ask_mode="off",
                    tag="exp1",
                )
            )
        return configs

    if experiment == "exp2":
        if not best_exp1:
            raise ValueError("exp2 requires best_exp1 parameters")
        pullback_window = [20, 50]
        pullback_threshold = [-1.0, -2.0, -3.0, -4.0]
        pullback_add_size = [5, 10, 15]
        pullback_cooldown_ticks = [5, 10, 20]
        configs = []
        for window, threshold, add_size, cooldown in itertools.product(
            pullback_window,
            pullback_threshold,
            pullback_add_size,
            pullback_cooldown_ticks,
        ):
            configs.append(
                PepperConfig(
                    opening_floor_pos=int(best_exp1["opening_floor_pos"]),
                    opening_floor_progress=float(best_exp1["opening_floor_progress"]),
                    opening_style=str(best_exp1["opening_style"]),
                    opening_taker_clip=int(best_exp1["opening_taker_clip"]),
                    opening_passive_clip=int(best_exp1["opening_passive_clip"]),
                    opening_passive_fill_ratio=float(best_exp1["opening_passive_fill_ratio"]),
                    passive_fill_ratio=float(best_exp1["opening_passive_fill_ratio"]),
                    main_target_pos=75,
                    late_target_pos=75,
                    pullback_window=window,
                    pullback_threshold=threshold,
                    pullback_add_size=add_size,
                    pullback_cooldown_ticks=cooldown,
                    bid_mode="one_level",
                    ask_mode="off",
                    tag="exp2",
                )
            )
        return configs

    if experiment == "exp3":
        if not best_exp1 or not best_exp2:
            raise ValueError("exp3 requires best_exp1 and best_exp2 parameters")
        hold_band = [3, 5]
        bid_mode = ["one_level", "two_level"]
        bid_aggressiveness = [1, 2]
        ask_mode = ["off", "tiny", "inventory_only"]
        ask_size_near_target = [0, 1, 2]
        ask_size_above_target = [2, 5]
        configs = []
        for hb, bid_m, bid_agg, ask_m, ask_near, ask_above in itertools.product(
            hold_band,
            bid_mode,
            bid_aggressiveness,
            ask_mode,
            ask_size_near_target,
            ask_size_above_target,
        ):
            if ask_m == "off" and ask_near != 0:
                continue
            configs.append(
                PepperConfig(
                    opening_floor_pos=int(best_exp1["opening_floor_pos"]),
                    opening_floor_progress=float(best_exp1["opening_floor_progress"]),
                    opening_style=str(best_exp1["opening_style"]),
                    opening_taker_clip=int(best_exp1["opening_taker_clip"]),
                    opening_passive_clip=int(best_exp1["opening_passive_clip"]),
                    opening_passive_fill_ratio=float(best_exp1["opening_passive_fill_ratio"]),
                    passive_fill_ratio=float(best_exp1["opening_passive_fill_ratio"]),
                    main_target_pos=75,
                    late_target_pos=75,
                    pullback_window=int(best_exp2["pullback_window"]),
                    pullback_threshold=float(best_exp2["pullback_threshold"]),
                    pullback_add_size=int(best_exp2["pullback_add_size"]),
                    pullback_cooldown_ticks=int(best_exp2["pullback_cooldown_ticks"]),
                    hold_band=hb,
                    bid_mode=bid_m,
                    bid_aggressiveness=bid_agg,
                    ask_mode=ask_m,
                    ask_size_near_target=ask_near,
                    ask_size_above_target=ask_above,
                    tag="exp3",
                )
            )
        return configs

    raise ValueError(f"unknown experiment: {experiment}")


def run_gridsearch(
    dataset: NormalizedDataset,
    experiment: str,
    configs: Iterable[PepperConfig],
    out_dir: Path,
) -> GridSearchResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    base_rows: List[Dict[str, object]] = []

    for idx, config in enumerate(configs):
        run_dir = out_dir / f"run_{idx:04d}"
        result = PepperExperimentRunner(dataset, config).run(out_dir=run_dir)
        row: Dict[str, object] = {**config.to_dict(), **result.metrics}
        row["run_dir"] = str(run_dir)
        base_rows.append(row)

    base_rows = sorted(base_rows, key=lambda row: float(row.get("final_equity", 0.0)), reverse=True)
    csv_path = out_dir / f"{experiment}_gridsearch.csv"
    json_path = out_dir / f"{experiment}_gridsearch.json"
    _write_rows(base_rows, csv_path, json_path)

    robust_rows = _build_robustness_rows(dataset, base_rows)
    summary_csv_path = out_dir / f"{experiment}_summary.csv"
    summary_json_path = out_dir / f"{experiment}_summary.json"
    _write_rows(robust_rows, summary_csv_path, summary_json_path)

    best_final_path = out_dir / f"{experiment}_best_by_final_equity.json"
    best_robust_path = out_dir / f"{experiment}_best_by_robust_score.json"
    best_final_path.write_text(json.dumps(base_rows[0] if base_rows else {}, indent=2), encoding="utf-8")
    best_robust_path.write_text(json.dumps(robust_rows[0] if robust_rows else {}, indent=2), encoding="utf-8")

    markdown_summary_path = out_dir / f"{experiment}_summary.md"
    markdown_summary_path.write_text(_build_markdown_summary(experiment, base_rows, robust_rows), encoding="utf-8")

    return GridSearchResult(
        experiment=experiment,
        rows=robust_rows,
        csv_path=csv_path,
        json_path=json_path,
        summary_csv_path=summary_csv_path,
        summary_json_path=summary_json_path,
        markdown_summary_path=markdown_summary_path,
        best_final_path=best_final_path,
        best_robust_path=best_robust_path,
    )


def _write_rows(rows: List[Dict[str, object]], csv_path: Path, json_path: Path) -> None:
    if rows:
        fieldnames = list(rows[0].keys())
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    else:
        csv_path.write_text("", encoding="utf-8")
        json_path.write_text("[]", encoding="utf-8")


def _build_robustness_rows(dataset: NormalizedDataset, base_rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    if not base_rows:
        return []

    scenario_lookup: Dict[str, Dict[str, Dict[str, object]]] = {}
    for scenario_name, fill_multiplier, trade_match_mode in ROBUSTNESS_SCENARIOS:
        rows: List[Dict[str, object]] = []
        for row in base_rows:
            config = _config_from_row(row)
            new_fill_ratio = max(0.0, min(1.0, float(config.passive_fill_ratio) * fill_multiplier))
            scenario_config = replace(
                config,
                passive_fill_ratio=new_fill_ratio,
                opening_passive_fill_ratio=new_fill_ratio,
                trade_match_mode=trade_match_mode,
                tag=f"{config.tag}:{scenario_name}",
            )
            result = PepperExperimentRunner(dataset, scenario_config).run(out_dir=None)
            scenario_row = {**row, **result.metrics}
            scenario_row["scenario_name"] = scenario_name
            scenario_row["scenario_trade_match_mode"] = trade_match_mode
            scenario_row["scenario_passive_fill_ratio"] = round(new_fill_ratio, 6)
            rows.append(scenario_row)

        rows.sort(key=lambda item: float(item.get("final_equity", 0.0)), reverse=True)
        lookup: Dict[str, Dict[str, object]] = {}
        for rank, row in enumerate(rows, start=1):
            row[f"rank_{scenario_name}"] = rank
            lookup[_row_key(row)] = row
        scenario_lookup[scenario_name] = lookup

    merged_rows: List[Dict[str, object]] = []
    for base_row in base_rows:
        merged = dict(base_row)
        rank_values: List[float] = []
        row_key = _row_key(base_row)
        for scenario_name, lookup in scenario_lookup.items():
            scenario_row = lookup[row_key]
            rank_value = float(scenario_row[f"rank_{scenario_name}"])
            rank_values.append(rank_value)
            merged[f"final_equity_{scenario_name}"] = scenario_row.get("final_equity")
            merged[f"trend_capture_ratio_{scenario_name}"] = scenario_row.get("trend_capture_ratio")
            merged[f"rank_{scenario_name}"] = int(rank_value)
        merged["robust_score"] = round(sum(rank_values) / len(rank_values), 6)
        merged_rows.append(merged)

    merged_rows.sort(key=lambda row: (float(row.get("robust_score", 1e18)), -float(row.get("final_equity", 0.0))))
    for rank, row in enumerate(merged_rows, start=1):
        row["rank_final_equity"] = _rank_in_base(base_rows, row)
        row["rank_robust_score"] = rank
    return merged_rows


def _rank_in_base(base_rows: List[Dict[str, object]], row: Dict[str, object]) -> int:
    row_dir = row.get("run_dir")
    for idx, base in enumerate(base_rows, start=1):
        if base.get("run_dir") == row_dir:
            return idx
    return len(base_rows)


def _config_from_row(row: Dict[str, object]) -> PepperConfig:
    allowed = set(PepperConfig.__dataclass_fields__.keys())
    kwargs = {key: row[key] for key in allowed if key in row}
    return PepperConfig(**kwargs)


def _row_key(row: Dict[str, object]) -> str:
    run_dir = row.get("run_dir")
    if run_dir is not None:
        return str(run_dir)
    return json.dumps({k: row[k] for k in sorted(row.keys()) if k != "run_dir"}, sort_keys=True, default=str)


def _build_markdown_summary(
    experiment: str,
    base_rows: List[Dict[str, object]],
    robust_rows: List[Dict[str, object]],
    top_k: int = 10,
) -> str:
    lines = [f"# {experiment.upper()} grid search summary", ""]
    lines.append("Execution assumptions used for robust_score:")
    lines.append("")
    for scenario_name, fill_multiplier, trade_match_mode in ROBUSTNESS_SCENARIOS:
        lines.append(
            f"- {scenario_name}: passive_fill_ratio x {fill_multiplier:.2f}, trade_match_mode={trade_match_mode}"
        )
    lines.append("")

    if base_rows:
        lines.append("## Best by final_equity")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(base_rows[0], indent=2))
        lines.append("```")
        lines.append("")

    if robust_rows:
        lines.append("## Best by robust_score")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(robust_rows[0], indent=2))
        lines.append("```")
        lines.append("")
        lines.append(f"## Top {min(top_k, len(robust_rows))} by robust_score")
        lines.append("")
        lines.append(
            "| rank_robust_score | rank_final_equity | robust_score | final_equity | trend_capture_ratio | run_dir |"
        )
        lines.append("|---:|---:|---:|---:|---:|---|")
        for row in robust_rows[:top_k]:
            lines.append(
                f"| {row.get('rank_robust_score')} | {row.get('rank_final_equity')} | "
                f"{float(row.get('robust_score', 0.0)):.3f} | {float(row.get('final_equity', 0.0)):.3f} | "
                f"{float(row.get('trend_capture_ratio', 0.0)):.3f} | {row.get('run_dir')} |"
            )
    else:
        lines.append("No rows were produced.")

    lines.append("")
    lines.append("Interpretation rule:")
    lines.append("- rank_final_equity answers: which config wins under the base assumption?")
    lines.append("- rank_robust_score answers: which config is most stable across multiple local execution assumptions?")
    return "\n".join(lines) + "\n"
