from __future__ import annotations

import json
from pathlib import Path

from imc_local_lab.backtester import Backtester
from imc_local_lab.loaders import load_day_dataset, load_submission_dataset
from imc_local_lab.trader_loader import load_trader_instance

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_backtester_generates_artifacts_for_day_dataset(tmp_path: Path) -> None:
    trader = load_trader_instance(FIXTURES / "sample_trader_impl.py")
    dataset = load_day_dataset(
        prices_csv=FIXTURES / "sample_prices.csv",
        trades_csv=FIXTURES / "sample_trades.csv",
        observations_csv=FIXTURES / "sample_observations.csv",
    )
    summary = Backtester(dataset).run(trader, tmp_path / "run_day")
    assert summary.tick_count == 2
    assert summary.artifacts.metrics_path.exists()
    assert summary.artifacts.submission_log_path.exists()
    payload = json.loads(summary.artifacts.submission_log_path.read_text(encoding="utf-8"))
    assert "activitiesLog" in payload
    assert isinstance(payload["tradeHistory"], list)


def test_backtester_generates_artifacts_for_submission_dataset(tmp_path: Path) -> None:
    trader = load_trader_instance(FIXTURES / "sample_trader_impl.py")
    dataset = load_submission_dataset(FIXTURES / "sample_submission.json")
    summary = Backtester(dataset).run(trader, tmp_path / "run_submission")
    assert summary.tick_count == 2
    payload = json.loads(summary.artifacts.trade_history_path.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
