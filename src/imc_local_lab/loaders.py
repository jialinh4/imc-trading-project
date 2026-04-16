from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from .dataset import (
    MarketTradeRow,
    NormalizedDataset,
    ObservationSnapshot,
    PriceLevel,
    ProductSnapshot,
    TickSnapshot,
)


def _parse_int(value: str) -> Optional[int]:
    value = value.strip()
    if value == "":
        return None
    return int(float(value))


def _parse_float(value: str) -> Optional[float]:
    value = value.strip()
    if value == "":
        return None
    return float(value)


def _book_levels(row: dict[str, str], pairs: List[tuple[str, str]]) -> List[PriceLevel]:
    levels: List[PriceLevel] = []
    for price_key, volume_key in pairs:
        price = _parse_int(row.get(price_key, ""))
        volume = _parse_int(row.get(volume_key, ""))
        if price is None or volume is None:
            continue
        levels.append(PriceLevel(price=price, volume=abs(volume)))
    return levels


def load_day_dataset(
    prices_csv: Path,
    trades_csv: Optional[Path] = None,
    observations_csv: Optional[Path] = None,
    dataset_id: Optional[str] = None,
) -> NormalizedDataset:
    prices_by_ts: Dict[tuple[Optional[int], int], Dict[str, ProductSnapshot]] = defaultdict(dict)
    products: set[str] = set()

    with prices_csv.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            day = _parse_int(row.get("day", ""))
            timestamp = _parse_int(row["timestamp"])
            assert timestamp is not None
            product = row["product"].strip()
            products.add(product)
            prices_by_ts[(day, timestamp)][product] = ProductSnapshot(
                product=product,
                bids=_book_levels(row, [("bid_price_1", "bid_volume_1"), ("bid_price_2", "bid_volume_2"), ("bid_price_3", "bid_volume_3")]),
                asks=_book_levels(row, [("ask_price_1", "ask_volume_1"), ("ask_price_2", "ask_volume_2"), ("ask_price_3", "ask_volume_3")]),
                mid_price=_parse_float(row.get("mid_price", "")),
            )

    trades_by_ts: Dict[tuple[Optional[int], int], Dict[str, List[MarketTradeRow]]] = defaultdict(lambda: defaultdict(list))
    if trades_csv is not None and trades_csv.exists():
        with trades_csv.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle, delimiter=";")
            for row in reader:
                timestamp = _parse_int(row["timestamp"])
                assert timestamp is not None
                symbol = row["symbol"].strip()
                products.add(symbol)
                trade = MarketTradeRow(
                    symbol=symbol,
                    price=int(float(row["price"])),
                    quantity=int(row["quantity"]),
                    buyer=row.get("buyer", "").strip(),
                    seller=row.get("seller", "").strip(),
                    timestamp=timestamp,
                    day=None,
                )
                trades_by_ts[(None, timestamp)][symbol].append(trade)

    observations_by_ts: Dict[int, ObservationSnapshot] = {}
    if observations_csv is not None and observations_csv.exists():
        with observations_csv.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                timestamp = int(row["timestamp"])
                observations_by_ts[timestamp] = ObservationSnapshot(
                    timestamp=timestamp,
                    plain={},
                    conversion={
                        "MAGNIFICENT_MACARONS": {
                            "bidPrice": float(row["bidPrice"]),
                            "askPrice": float(row["askPrice"]),
                            "transportFees": float(row["transportFees"]),
                            "exportTariff": float(row["exportTariff"]),
                            "importTariff": float(row["importTariff"]),
                            "sugarPrice": float(row["sugarPrice"]),
                            "sunlightIndex": float(row["sunlightIndex"]),
                        }
                    },
                )

    ticks: List[TickSnapshot] = []
    for (day, timestamp), product_map in sorted(prices_by_ts.items(), key=lambda item: ((item[0][0] is None, item[0][0]), item[0][1])):
        market_trades = trades_by_ts.get((day, timestamp)) or trades_by_ts.get((None, timestamp)) or {}
        observation = observations_by_ts.get(timestamp, ObservationSnapshot(timestamp=timestamp))
        ticks.append(
            TickSnapshot(
                timestamp=timestamp,
                day=day,
                products=dict(sorted(product_map.items())),
                market_trades={symbol: list(rows) for symbol, rows in market_trades.items()},
                observations=observation,
            )
        )

    return NormalizedDataset(
        dataset_id=dataset_id or prices_csv.stem,
        source=str(prices_csv),
        products=sorted(products),
        ticks=ticks,
        metadata={"kind": "day_csv"},
    )


def load_submission_dataset(submission_path: Path, dataset_id: Optional[str] = None) -> NormalizedDataset:
    payload = json.loads(submission_path.read_text(encoding="utf-8"))
    activities_log = payload.get("activitiesLog", "")
    trade_history = payload.get("tradeHistory", [])

    prices_by_ts: Dict[tuple[Optional[int], int], Dict[str, ProductSnapshot]] = defaultdict(dict)
    products: set[str] = set()

    for line_index, line in enumerate(activities_log.splitlines()):
        if line_index == 0 or not line.strip():
            continue
        parts = line.split(";")
        if len(parts) < 17:
            continue
        day = _parse_int(parts[0])
        timestamp = int(parts[1])
        product = parts[2].strip()
        products.add(product)
        row = {
            "bid_price_1": parts[3],
            "bid_volume_1": parts[4],
            "bid_price_2": parts[5],
            "bid_volume_2": parts[6],
            "bid_price_3": parts[7],
            "bid_volume_3": parts[8],
            "ask_price_1": parts[9],
            "ask_volume_1": parts[10],
            "ask_price_2": parts[11],
            "ask_volume_2": parts[12],
            "ask_price_3": parts[13],
            "ask_volume_3": parts[14],
            "mid_price": parts[15],
        }
        prices_by_ts[(day, timestamp)][product] = ProductSnapshot(
            product=product,
            bids=_book_levels(row, [("bid_price_1", "bid_volume_1"), ("bid_price_2", "bid_volume_2"), ("bid_price_3", "bid_volume_3")]),
            asks=_book_levels(row, [("ask_price_1", "ask_volume_1"), ("ask_price_2", "ask_volume_2"), ("ask_price_3", "ask_volume_3")]),
            mid_price=_parse_float(parts[15]),
        )

    trades_by_ts: Dict[tuple[Optional[int], int], Dict[str, List[MarketTradeRow]]] = defaultdict(lambda: defaultdict(list))
    for row in trade_history:
        symbol = row.get("symbol", "").strip()
        if not symbol:
            continue
        products.add(symbol)
        trade = MarketTradeRow(
            symbol=symbol,
            price=int(float(row["price"])),
            quantity=int(row["quantity"]),
            buyer=str(row.get("buyer", "")),
            seller=str(row.get("seller", "")),
            timestamp=int(row["timestamp"]),
            day=row.get("day"),
        )
        trades_by_ts[(trade.day, trade.timestamp)][symbol].append(trade)

    ticks: List[TickSnapshot] = []
    for (day, timestamp), product_map in sorted(prices_by_ts.items(), key=lambda item: ((item[0][0] is None, item[0][0]), item[0][1])):
        market_trades = trades_by_ts.get((day, timestamp)) or trades_by_ts.get((None, timestamp)) or {}
        ticks.append(
            TickSnapshot(
                timestamp=timestamp,
                day=day,
                products=dict(sorted(product_map.items())),
                market_trades={symbol: list(rows) for symbol, rows in market_trades.items()},
                observations=ObservationSnapshot(timestamp=timestamp),
            )
        )

    return NormalizedDataset(
        dataset_id=dataset_id or submission_path.stem,
        source=str(submission_path),
        products=sorted(products),
        ticks=ticks,
        metadata={
            "kind": "submission_log",
            "submissionId": payload.get("submissionId"),
        },
    )


def load_dataset_auto(path: Path, dataset_id: Optional[str] = None) -> NormalizedDataset:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return load_day_dataset(prices_csv=path, dataset_id=dataset_id)
    if suffix in {".json", ".log"}:
        return load_submission_dataset(submission_path=path, dataset_id=dataset_id)
    raise ValueError(f"unsupported dataset path: {path}")
