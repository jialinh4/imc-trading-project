from __future__ import annotations

from pathlib import Path

from imc_local_lab.loaders import load_day_dataset, load_submission_dataset

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_load_day_dataset_smoke() -> None:
    dataset = load_day_dataset(
        prices_csv=FIXTURES / "sample_prices.csv",
        trades_csv=FIXTURES / "sample_trades.csv",
        observations_csv=FIXTURES / "sample_observations.csv",
    )
    assert dataset.dataset_id == "sample_prices"
    assert dataset.products == ["EMERALDS", "TOMATOES"]
    assert len(dataset.ticks) == 2
    assert dataset.ticks[0].products["EMERALDS"].bids[0].price == 9998
    assert dataset.ticks[0].observations.conversion["MAGNIFICENT_MACARONS"]["bidPrice"] == 100.0


def test_load_submission_dataset_smoke() -> None:
    dataset = load_submission_dataset(FIXTURES / "sample_submission.json")
    assert dataset.dataset_id == "sample_submission"
    assert len(dataset.ticks) == 2
    assert dataset.ticks[0].day == -1
    assert dataset.ticks[0].market_trades["EMERALDS"][0].price == 10001
