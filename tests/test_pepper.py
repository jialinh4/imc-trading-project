from __future__ import annotations

from pathlib import Path

from imc_local_lab.dataset import MarketTradeRow, NormalizedDataset, ObservationSnapshot, PriceLevel, ProductSnapshot, TickSnapshot
from imc_local_lab.pepper import PepperConfig, PepperExperimentRunner, grid_for_experiment, run_gridsearch


def build_pepper_dataset() -> NormalizedDataset:
    ticks = []
    mids = [100.0, 101.0, 103.0, 102.0, 104.0]
    timestamps = [0, 100, 200, 300, 400]
    for idx, (ts, mid) in enumerate(zip(timestamps, mids)):
        ticks.append(
            TickSnapshot(
                timestamp=ts,
                day=-1,
                products={
                    "INTARIAN_PEPPER_ROOT": ProductSnapshot(
                        product="INTARIAN_PEPPER_ROOT",
                        bids=[PriceLevel(price=int(mid - 1), volume=10), PriceLevel(price=int(mid - 2), volume=8)],
                        asks=[PriceLevel(price=int(mid + 1), volume=10), PriceLevel(price=int(mid + 2), volume=8)],
                        mid_price=mid,
                    )
                },
                market_trades={
                    "INTARIAN_PEPPER_ROOT": [
                        MarketTradeRow(
                            symbol="INTARIAN_PEPPER_ROOT",
                            price=int(mid - 1 if idx % 2 == 0 else mid + 1),
                            quantity=6,
                            buyer="A",
                            seller="B",
                            timestamp=ts,
                            day=-1,
                        )
                    ]
                },
                observations=ObservationSnapshot(timestamp=ts),
            )
        )
    return NormalizedDataset(
        dataset_id="pepper_test",
        source="synthetic",
        products=["INTARIAN_PEPPER_ROOT"],
        ticks=ticks,
    )


def test_pepper_runner_emits_metrics_and_artifacts(tmp_path: Path) -> None:
    dataset = build_pepper_dataset()
    config = PepperConfig(
        opening_floor_pos=40,
        opening_floor_progress=0.2,
        opening_style="taker",
        opening_taker_clip=10,
        main_target_pos=60,
        late_target_pos=60,
        ask_mode="off",
    )
    result = PepperExperimentRunner(dataset, config).run(out_dir=tmp_path / "pepper_run")
    assert result.metrics["dataset_id"] == "pepper_test"
    assert "final_equity" in result.metrics
    assert result.artifacts is not None
    assert result.artifacts.metrics_path.exists()
    assert result.artifacts.fills_path.exists()


def test_pepper_gridsearch_smoke(tmp_path: Path) -> None:
    dataset = build_pepper_dataset()
    configs = [
        PepperConfig(opening_floor_pos=40, opening_style="taker", tag="a"),
        PepperConfig(opening_floor_pos=60, opening_style="passive", tag="b"),
    ]
    result = run_gridsearch(dataset, "exp1", configs, tmp_path / "grid")
    assert len(result.rows) == 2
    assert result.csv_path is not None and result.csv_path.exists()
    assert result.json_path is not None and result.json_path.exists()
    assert result.summary_csv_path is not None and result.summary_csv_path.exists()
    assert result.summary_json_path is not None and result.summary_json_path.exists()
    assert result.markdown_summary_path is not None and result.markdown_summary_path.exists()
    assert result.best_final_path is not None and result.best_final_path.exists()
    assert result.best_robust_path is not None and result.best_robust_path.exists()
    assert "robust_score" in result.rows[0]
    assert "rank_final_equity" in result.rows[0]
    assert "rank_robust_score" in result.rows[0]


def test_exp_grids_have_expected_sizes() -> None:
    exp1 = grid_for_experiment("exp1")
    assert len(exp1) == 144
    best_exp1 = exp1[0].to_dict()
    exp2 = grid_for_experiment("exp2", best_exp1=best_exp1)
    assert len(exp2) == 72
    best_exp2 = exp2[0].to_dict()
    exp3 = grid_for_experiment("exp3", best_exp1=best_exp1, best_exp2=best_exp2)
    assert len(exp3) > 0
