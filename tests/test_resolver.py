from __future__ import annotations

from pathlib import Path

from imc_local_lab.resolver import parse_day_selectors, resolve_selections


FIXTURES_ROOT = Path(__file__).resolve().parent.parent / "datasets"


def test_parse_day_selectors_basic() -> None:
    parsed = parse_day_selectors(["0", "1-0", "1--1", "1-submission"], FIXTURES_ROOT)
    assert (0, None, "round") in parsed
    assert (1, 0, "day") in parsed
    assert (1, -1, "day") in parsed
    assert (1, None, "submission") in parsed


def test_resolve_selections_tutorial_smoke() -> None:
    selections = resolve_selections(FIXTURES_ROOT, ["0", "0-submission"])
    labels = [item.label for item in selections]
    assert "round0_day_-1" in labels
    assert "round0_submission" in labels
