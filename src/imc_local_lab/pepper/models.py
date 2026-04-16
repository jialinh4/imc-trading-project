from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class PepperConfig:
    product: str = "INTARIAN_PEPPER_ROOT"
    position_limit: int = 80

    opening_floor_pos: int = 60
    opening_floor_progress: float = 0.05
    opening_style: str = "taker"  # taker | passive | hybrid
    opening_taker_clip: int = 10
    opening_passive_clip: int = 5
    opening_passive_fill_ratio: float = 0.25

    main_target_pos: int = 75
    late_target_pos: int = 75
    late_progress: float = 0.60

    pullback_window: int = 20
    pullback_threshold: float = -2.0
    pullback_add_size: int = 10
    pullback_cooldown_ticks: int = 10

    hold_band: int = 5
    bid_mode: str = "one_level"  # one_level | two_level
    bid_aggressiveness: int = 1
    ask_mode: str = "off"  # off | tiny | inventory_only
    ask_size_near_target: int = 0
    ask_size_above_target: int = 2
    inventory_trim_threshold: int = 78
    clear_to_pos: int = 75

    passive_fill_ratio: float = 0.25
    passive_two_level_back_ratio: float = 0.4
    trade_match_mode: str = "all"

    tag: str = "manual"

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class PepperOrderIntent:
    symbol: str
    price: int
    quantity: int
    style: str  # taker | passive
    reason: str
    level: str = "primary"


@dataclass
class PepperFillEvent:
    timestamp: int
    index: int
    symbol: str
    price: int
    quantity: int
    side: str  # buy | sell
    style: str
    reason: str
    level: str
    progress: float
    mid_price: float
    pullback: float


@dataclass
class PepperRunArtifacts:
    summary_path: Path
    fills_path: Path
    inventory_path: Path
    metrics_path: Path


@dataclass
class PepperRunResult:
    config: PepperConfig
    metrics: Dict[str, float | int | str | None]
    fills: List[PepperFillEvent]
    artifacts: Optional[PepperRunArtifacts] = None


@dataclass
class GridSearchResult:
    experiment: str
    rows: List[Dict[str, object]] = field(default_factory=list)
    csv_path: Optional[Path] = None
    json_path: Optional[Path] = None
    summary_csv_path: Optional[Path] = None
    summary_json_path: Optional[Path] = None
    markdown_summary_path: Optional[Path] = None
    best_final_path: Optional[Path] = None
    best_robust_path: Optional[Path] = None
