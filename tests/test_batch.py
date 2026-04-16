from __future__ import annotations

import json
from pathlib import Path

from imc_local_lab.batch import run_selections
from imc_local_lab.resolver import resolve_selections


DATASETS = Path(__file__).resolve().parent.parent / "datasets"
EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_run_selections_independent_writes_batch_summary(tmp_path: Path) -> None:
    selections = resolve_selections(DATASETS, ["0", "0-submission"])
    result = run_selections(
        selections=selections,
        trader_path=EXAMPLES / "sample_trader.py",
        out_dir=tmp_path / "batch",
    )
    assert result.summary_path.exists()
    payload = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert payload["num_runs"] == 2


def test_run_selections_carry_writes_merged_summary(tmp_path: Path) -> None:
    selections = resolve_selections(DATASETS, ["0"])
    result = run_selections(
        selections=selections,
        trader_path=EXAMPLES / "sample_trader.py",
        out_dir=tmp_path / "batch_carry",
        carry_state=True,
    )
    assert result.summary_path.exists()
    payload = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert payload["mode"] == "carry"
