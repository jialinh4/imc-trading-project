from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List

from .models import PepperConfig, PepperOrderIntent


@dataclass
class PepperPolicyState:
    high_window: Deque[float] = field(default_factory=deque)
    last_pullback_add_index: int = -10**9


class PepperPolicy:
    def __init__(self, config: PepperConfig):
        self.config = config
        self.state = PepperPolicyState()

    def step(
        self,
        *,
        index: int,
        progress: float,
        position: int,
        best_bid: int,
        best_ask: int,
        best_bid_volume: int,
        best_ask_volume: int,
        mid_price: float,
    ) -> tuple[List[PepperOrderIntent], dict[str, float | int | str]]:
        cfg = self.config
        info: dict[str, float | int | str] = {}
        intents: List[PepperOrderIntent] = []

        window = self.state.high_window
        window.append(mid_price)
        while len(window) > max(1, cfg.pullback_window):
            window.popleft()
        rolling_high = max(window) if window else mid_price
        pullback = mid_price - rolling_high

        base_target = cfg.main_target_pos if progress < cfg.late_progress else cfg.late_target_pos
        info["base_target"] = base_target
        info["pullback"] = pullback

        # Opening floor phase
        floor_active = progress <= cfg.opening_floor_progress and position < cfg.opening_floor_pos
        if floor_active:
            missing = cfg.opening_floor_pos - position
            if cfg.opening_style == "taker":
                qty = min(cfg.opening_taker_clip, missing)
                if qty > 0:
                    intents.append(self._buy(best_ask, qty, "taker", "opening_floor", "primary"))
            elif cfg.opening_style == "passive":
                qty = min(cfg.opening_passive_clip, missing)
                if qty > 0:
                    px = self._aggressive_bid(best_bid, best_ask, cfg.bid_aggressiveness)
                    intents.append(self._buy(px, qty, "passive", "opening_floor", "primary"))
            elif cfg.opening_style == "hybrid":
                hybrid_taker_floor = max(1, cfg.opening_floor_pos // 2)
                if position < hybrid_taker_floor:
                    qty = min(cfg.opening_taker_clip, hybrid_taker_floor - position)
                    if qty > 0:
                        intents.append(self._buy(best_ask, qty, "taker", "opening_floor", "primary"))
                else:
                    qty = min(cfg.opening_passive_clip, missing)
                    if qty > 0:
                        px = self._aggressive_bid(best_bid, best_ask, cfg.bid_aggressiveness)
                        intents.append(self._buy(px, qty, "passive", "opening_floor", "primary"))

        # Pullback add: stateful cooldown
        can_pullback_add = (
            pullback <= cfg.pullback_threshold
            and index - self.state.last_pullback_add_index >= cfg.pullback_cooldown_ticks
            and position < cfg.position_limit
        )
        if can_pullback_add:
            add_qty = min(cfg.pullback_add_size, cfg.position_limit - position)
            if add_qty > 0:
                intents.append(self._buy(best_ask, add_qty, "taker", "pullback_add", "primary"))
                self.state.last_pullback_add_index = index

        effective_target = min(cfg.position_limit, base_target)
        gap = effective_target - position
        info["target_pos"] = effective_target
        info["gap"] = gap

        # Hold / replenishment overlay on the bid side
        if gap > 0:
            if cfg.bid_mode == "one_level":
                qty = min(max(1, gap), cfg.position_limit - position)
                if qty > 0:
                    px = self._aggressive_bid(best_bid, best_ask, cfg.bid_aggressiveness)
                    intents.append(self._buy(px, qty, "passive", "hold_replenish", "primary"))
            elif cfg.bid_mode == "two_level":
                qty = min(max(1, gap), cfg.position_limit - position)
                if qty > 0:
                    front_qty = max(1, int(round(qty * 0.6)))
                    back_qty = max(0, qty - front_qty)
                    front_px = self._aggressive_bid(best_bid, best_ask, cfg.bid_aggressiveness)
                    intents.append(self._buy(front_px, front_qty, "passive", "hold_replenish", "front"))
                    if back_qty > 0:
                        back_px = max(best_bid, front_px - 1)
                        intents.append(self._buy(back_px, back_qty, "passive", "hold_replenish", "back"))

        # Ask side behavior
        if position >= cfg.inventory_trim_threshold:
            trim_qty = min(position - cfg.clear_to_pos, cfg.position_limit + position)
            if trim_qty > 0:
                intents.append(self._sell(best_bid, trim_qty, "taker", "trim", "primary"))
        elif cfg.ask_mode == "tiny" and position >= effective_target - cfg.hold_band and cfg.ask_size_near_target > 0:
            intents.append(
                self._sell(max(best_ask, best_bid + 1), cfg.ask_size_near_target, "passive", "tiny_ask", "primary")
            )
        elif cfg.ask_mode == "inventory_only" and position > effective_target + cfg.hold_band and cfg.ask_size_above_target > 0:
            intents.append(
                self._sell(max(best_ask, best_bid + 1), cfg.ask_size_above_target, "passive", "inventory_only_ask", "primary")
            )

        info["progress"] = progress
        return intents, info

    def _aggressive_bid(self, best_bid: int, best_ask: int, aggressiveness: int) -> int:
        return min(best_ask - 1, best_bid + max(1, aggressiveness))

    def _buy(self, price: int, quantity: int, style: str, reason: str, level: str) -> PepperOrderIntent:
        return PepperOrderIntent(
            symbol=self.config.product,
            price=int(price),
            quantity=int(quantity),
            style=style,
            reason=reason,
            level=level,
        )

    def _sell(self, price: int, quantity: int, style: str, reason: str, level: str) -> PepperOrderIntent:
        return PepperOrderIntent(
            symbol=self.config.product,
            price=int(price),
            quantity=-int(quantity),
            style=style,
            reason=reason,
            level=level,
        )
