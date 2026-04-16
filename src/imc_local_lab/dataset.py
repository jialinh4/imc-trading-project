from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class PriceLevel:
    price: int
    volume: int


@dataclass
class ProductSnapshot:
    product: str
    bids: List[PriceLevel]
    asks: List[PriceLevel]
    mid_price: Optional[float]


@dataclass
class MarketTradeRow:
    symbol: str
    price: int
    quantity: int
    buyer: str
    seller: str
    timestamp: int
    day: Optional[int] = None


@dataclass
class ObservationSnapshot:
    timestamp: int
    plain: Dict[str, int] = field(default_factory=dict)
    conversion: Dict[str, Dict[str, float]] = field(default_factory=dict)


@dataclass
class TickSnapshot:
    timestamp: int
    day: Optional[int]
    products: Dict[str, ProductSnapshot]
    market_trades: Dict[str, List[MarketTradeRow]] = field(default_factory=dict)
    observations: ObservationSnapshot = field(default_factory=lambda: ObservationSnapshot(timestamp=0))


@dataclass
class NormalizedDataset:
    dataset_id: str
    source: str
    products: List[str]
    ticks: List[TickSnapshot]
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass
class BacktestArtifacts:
    metrics_path: Path
    submission_log_path: Path
    activities_csv_path: Path
    sandbox_logs_path: Path
    trade_history_path: Path


@dataclass
class BacktestSummary:
    dataset_id: str
    tick_count: int
    final_pnl_total: float
    final_pnl_by_product: Dict[str, float]
    artifacts: BacktestArtifacts
