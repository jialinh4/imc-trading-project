from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .dataset import NormalizedDataset, TickSnapshot
from .loaders import load_day_dataset, load_submission_dataset


@dataclass
class DatasetSelection:
    label: str
    dataset: NormalizedDataset
    source_path: Path
    day: Optional[int]
    round_number: Optional[int]
    kind: str


def default_datasets_root(package_root: Path) -> Path:
    root = package_root.parent.parent
    return root / "datasets"


def default_trader_roots(package_root: Path) -> list[Path]:
    root = package_root.parent.parent
    return [root / "traders", root / "scripts", root]


def find_latest_round_root(datasets_root: Path) -> Path:
    candidates: list[tuple[int, Path]] = []
    tutorial = datasets_root / "tutorial"
    if tutorial.exists():
        candidates.append((0, tutorial))
    for i in range(1, 9):
        round_dir = datasets_root / f"round{i}"
        if round_dir.exists():
            candidates.append((i, round_dir))
    populated = []
    for num, path in candidates:
        if list(path.glob("prices_round_*_day_*.csv")) or list(path.glob("submission.*")):
            populated.append((num, path))
    if not populated:
        raise FileNotFoundError(f"no round data found under {datasets_root}")
    return sorted(populated, key=lambda x: x[0])[-1][1]


def auto_pick_trader(trader_roots: Iterable[Path]) -> Path:
    candidates: list[Path] = []
    for root in trader_roots:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if path.name.startswith("test_"):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            if "class Trader" in text:
                candidates.append(path)
    if not candidates:
        raise FileNotFoundError("no trader file found automatically")
    candidates.sort(key=lambda p: p.stat().st_mtime)
    return candidates[-1]


def parse_limit_overrides(values: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in values:
        if ":" not in item:
            raise ValueError(f"invalid --limit value: {item!r}")
        product, raw = item.split(":", 1)
        out[product.strip()] = int(raw.strip())
    return out


def parse_day_selectors(selectors: list[str], datasets_root: Path, include_submission: bool = False) -> list[tuple[int, Optional[int], str]]:
    if not selectors:
        latest = find_latest_round_root(datasets_root)
        name = latest.name
        if name == 'tutorial':
            return [(0, None, 'round')]
        if name.startswith('round'):
            return [(int(name.removeprefix('round')), None, 'round')]
        raise ValueError(f"cannot infer round from {latest}")
    out = []
    for selector in selectors:
        if selector in {'tutorial', '0'}:
            out.append((0, None, 'round'))
            continue
        if selector.endswith('-submission'):
            round_part = selector[:-11]
            rnd = 0 if round_part in {'tutorial', '0'} else int(round_part)
            out.append((rnd, None, 'submission'))
            continue
        m = None
        if '--' in selector:
            left, right = selector.split('--', 1)
            if left.isdigit() and right.isdigit():
                out.append((int(left), -int(right), 'day'))
                continue
        if '-' in selector:
            left, right = selector.split('-', 1)
            if left.isdigit() and right.lstrip('-').isdigit():
                out.append((int(left), int(right), 'day'))
                continue
        if selector.isdigit():
            out.append((int(selector), None, 'round'))
            continue
        raise ValueError(f"unsupported day selector: {selector}")
    if include_submission:
        seen = {(r, k) for r, _, k in out if k == 'submission'}
        for r, _, kind in list(out):
            if kind == 'round' and (r, 'submission') not in seen:
                out.append((r, None, 'submission'))
    return out


def resolve_round_dir(datasets_root: Path, round_number: int) -> Path:
    if round_number == 0:
        tutorial = datasets_root / 'tutorial'
        round0 = datasets_root / 'round0'
        if tutorial.exists():
            return tutorial
        if round0.exists():
            return round0
    round_dir = datasets_root / f'round{round_number}'
    if round_dir.exists():
        return round_dir
    raise FileNotFoundError(f"round directory not found for round {round_number}: {round_dir}")


def _day_file_map(round_dir: Path) -> dict[int, Path]:
    out: dict[int, Path] = {}
    for path in round_dir.glob('prices_round_*_day_*.csv'):
        stem = path.stem
        day_token = stem.split('_day_')[-1]
        out[int(day_token)] = path
    return out


def _submission_path(round_dir: Path) -> Optional[Path]:
    for name in ['submission.json', 'submission.log']:
        path = round_dir / name
        if path.exists():
            return path
    return None


def resolve_selections(datasets_root: Path, selectors: list[str], include_submission: bool = False) -> list[DatasetSelection]:
    parsed = parse_day_selectors(selectors, datasets_root, include_submission=include_submission)
    selections: list[DatasetSelection] = []
    for round_number, day, kind in parsed:
        round_dir = resolve_round_dir(datasets_root, round_number)
        if kind == 'submission':
            submission = _submission_path(round_dir)
            if submission is None:
                continue
            dataset = load_submission_dataset(submission, dataset_id=f"round{round_number}_submission")
            selections.append(DatasetSelection(
                label=f"round{round_number}_submission",
                dataset=dataset,
                source_path=submission,
                day=None,
                round_number=round_number,
                kind='submission',
            ))
            continue
        day_map = _day_file_map(round_dir)
        selected_days = [day] if kind == 'day' else sorted(day_map)
        for day_value in selected_days:
            prices = day_map.get(day_value)
            if prices is None:
                continue
            trades = prices.with_name(prices.name.replace('prices_', 'trades_', 1))
            observations = prices.with_name(prices.name.replace('prices_', 'observations_', 1))
            dataset = load_day_dataset(
                prices_csv=prices,
                trades_csv=trades if trades.exists() else None,
                observations_csv=observations if observations.exists() else None,
                dataset_id=f"round{round_number}_day_{day_value}",
            )
            selections.append(DatasetSelection(
                label=f"round{round_number}_day_{day_value}",
                dataset=dataset,
                source_path=prices,
                day=day_value,
                round_number=round_number,
                kind='day',
            ))
    if not selections:
        raise FileNotFoundError(f"no matching datasets found under {datasets_root}")
    selections.sort(key=lambda s: (s.round_number or -1, s.day if s.day is not None else 10**9, s.kind))
    return selections


def merge_datasets(selections: list[DatasetSelection], dataset_id: str, carry_state: bool = False) -> NormalizedDataset:
    products = sorted({product for sel in selections for product in sel.dataset.products})
    ticks: list[TickSnapshot] = []
    timestamp_offset = 0
    for index, selection in enumerate(selections):
        local_ticks = [tick for tick in selection.dataset.ticks]
        if carry_state and index > 0 and local_ticks:
            base = local_ticks[0].timestamp
            adjusted = []
            for tick in local_ticks:
                delta = tick.timestamp - base
                adjusted_trades = {
                    symbol: [
                        type(trade)(
                            symbol=trade.symbol,
                            price=trade.price,
                            quantity=trade.quantity,
                            buyer=trade.buyer,
                            seller=trade.seller,
                            timestamp=timestamp_offset + delta,
                            day=trade.day,
                        )
                        for trade in rows
                    ]
                    for symbol, rows in tick.market_trades.items()
                }
                adjusted.append(TickSnapshot(
                    timestamp=timestamp_offset + delta,
                    day=tick.day,
                    products=tick.products,
                    market_trades=adjusted_trades,
                    observations=tick.observations,
                ))
            local_ticks = adjusted
            timestamp_offset = local_ticks[-1].timestamp + 100
        ticks.extend(local_ticks)
        if not carry_state and local_ticks:
            timestamp_offset = max(timestamp_offset, local_ticks[-1].timestamp + 100)
    ticks.sort(key=lambda t: ((t.day is None, t.day), t.timestamp))
    return NormalizedDataset(
        dataset_id=dataset_id,
        source='merged',
        products=products,
        ticks=ticks,
        metadata={
            'kind': 'merged',
            'carry_state': carry_state,
            'sources': [str(sel.source_path) for sel in selections],
        },
    )
