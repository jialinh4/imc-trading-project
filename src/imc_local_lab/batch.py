from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from .backtester import Backtester
from .resolver import DatasetSelection, merge_datasets
from .trader_loader import load_trader_instance


@dataclass
class BatchRunResult:
    mode: str
    outputs: list[dict]
    summary_path: Path
    markdown_path: Path


def _write_batch_summary(out_dir: Path, mode: str, rows: list[dict]) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "batch_summary.json"
    markdown_path = out_dir / "batch_summary.md"
    payload = {
        "mode": mode,
        "num_runs": len(rows),
        "runs": rows,
        "final_pnl_total": sum(float(row["final_pnl_total"]) for row in rows),
    }
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md_lines = [
        "# Batch Summary",
        "",
        f"- mode: `{mode}`",
        f"- runs: {len(rows)}",
        f"- total final pnl: {payload['final_pnl_total']:.2f}",
        "",
        "| label | tick_count | final_pnl_total | out_dir |",
        "|---|---:|---:|---|",
    ]
    for row in rows:
        md_lines.append(
            f"| {row['label']} | {row['tick_count']} | {row['final_pnl_total']:.2f} | `{row['out_dir']}` |"
        )
    markdown_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return summary_path, markdown_path


def run_selections(
    selections: list[DatasetSelection],
    trader_path: Path,
    out_dir: Path,
    trade_match_mode: str = "all",
    position_limits: Optional[Dict[str, int]] = None,
    carry_state: bool = False,
) -> BatchRunResult:
    rows: list[dict] = []
    if carry_state:
        trader = load_trader_instance(trader_path)
        merged = merge_datasets(selections, dataset_id="carry_merged", carry_state=True)
        merged_out = out_dir / "carry_merged"
        summary = Backtester(merged, position_limits=position_limits, trade_match_mode=trade_match_mode).run(trader, merged_out)
        rows.append({
            "label": "carry_merged",
            "dataset_id": summary.dataset_id,
            "tick_count": summary.tick_count,
            "final_pnl_total": summary.final_pnl_total,
            "final_pnl_by_product": summary.final_pnl_by_product,
            "out_dir": str(merged_out),
        })
        summary_path, markdown_path = _write_batch_summary(out_dir, "carry", rows)
        return BatchRunResult(mode="carry", outputs=rows, summary_path=summary_path, markdown_path=markdown_path)

    for selection in selections:
        trader = load_trader_instance(trader_path)
        run_out = out_dir / selection.label
        summary = Backtester(selection.dataset, position_limits=position_limits, trade_match_mode=trade_match_mode).run(trader, run_out)
        rows.append({
            "label": selection.label,
            "dataset_id": summary.dataset_id,
            "tick_count": summary.tick_count,
            "final_pnl_total": summary.final_pnl_total,
            "final_pnl_by_product": summary.final_pnl_by_product,
            "out_dir": str(run_out),
        })
    summary_path, markdown_path = _write_batch_summary(out_dir, "independent", rows)
    return BatchRunResult(mode="independent", outputs=rows, summary_path=summary_path, markdown_path=markdown_path)
