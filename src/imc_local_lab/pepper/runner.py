from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional

from ..dataset import NormalizedDataset, TickSnapshot
from .models import PepperConfig, PepperFillEvent, PepperOrderIntent, PepperRunArtifacts, PepperRunResult
from .policy import PepperPolicy


class PepperExperimentRunner:
    def __init__(self, dataset: NormalizedDataset, config: PepperConfig):
        self.dataset = dataset
        self.config = config
        self.product = config.product
        self.position_limit = config.position_limit

    def run(self, out_dir: Optional[Path] = None) -> PepperRunResult:
        ticks = [tick for tick in self.dataset.ticks if self.product in tick.products]
        if not ticks:
            raise ValueError(f"product {self.product} was not found in dataset {self.dataset.dataset_id}")

        policy = PepperPolicy(self.config)
        fills: List[PepperFillEvent] = []
        inventory_rows: List[dict] = []
        position = 0
        realized_pnl = 0.0
        passive_posted_qty = 0
        passive_filled_qty = 0
        taker_filled_qty = 0
        buy_prices: List[tuple[int, int]] = []
        opening_buy_prices: List[tuple[int, int]] = []
        pullback_add_prices: List[tuple[int, int]] = []
        sell_volume_total = 0
        sell_volume_unnecessary = 0
        pullback_events: List[dict] = []
        replenishment_posted = 0
        replenishment_filled = 0
        pnl_capture_terms: List[float] = []
        ideal_capture_terms: List[float] = []

        last_mid = ticks[0].products[self.product].mid_price or 0.0

        for index, tick in enumerate(ticks):
            snapshot = tick.products[self.product]
            best_bid = snapshot.bids[0].price if snapshot.bids else 0
            best_ask = snapshot.asks[0].price if snapshot.asks else best_bid
            best_bid_vol = snapshot.bids[0].volume if snapshot.bids else 0
            best_ask_vol = snapshot.asks[0].volume if snapshot.asks else 0
            mid = float(snapshot.mid_price if snapshot.mid_price is not None else (best_bid + best_ask) / 2.0)
            progress = index / max(1, len(ticks) - 1)

            mid_diff = mid - last_mid
            pnl_capture_terms.append(position * mid_diff)
            ideal_capture_terms.append(self.position_limit * max(0.0, mid_diff))
            last_mid = mid

            intents, info = policy.step(
                index=index,
                progress=progress,
                position=position,
                best_bid=best_bid,
                best_ask=best_ask,
                best_bid_volume=best_bid_vol,
                best_ask_volume=best_ask_vol,
                mid_price=mid,
            )

            for intent in intents:
                if intent.style == "passive":
                    passive_posted_qty += abs(intent.quantity)
                if intent.reason == "hold_replenish":
                    replenishment_posted += max(0, intent.quantity)

            tick_fills = self._execute_tick(index, tick, intents, progress, float(info.get("pullback", 0.0)), mid)
            for fill in tick_fills:
                fills.append(fill)
                signed_qty = fill.quantity if fill.side == "buy" else -fill.quantity
                position += signed_qty
                realized_pnl += (-fill.price * fill.quantity) if fill.side == "buy" else (fill.price * fill.quantity)

                if fill.style == "passive":
                    passive_filled_qty += fill.quantity
                else:
                    taker_filled_qty += fill.quantity

                if fill.side == "buy":
                    buy_prices.append((fill.price, fill.quantity))
                    if fill.reason == "opening_floor":
                        opening_buy_prices.append((fill.price, fill.quantity))
                    if fill.reason == "pullback_add":
                        pullback_add_prices.append((fill.price, fill.quantity))
                        pullback_events.append({
                            "index": fill.index,
                            "price": fill.price,
                            "quantity": fill.quantity,
                            "pullback": fill.pullback,
                        })
                    if fill.reason == "hold_replenish":
                        replenishment_filled += fill.quantity
                else:
                    sell_volume_total += fill.quantity
                    if fill.reason != "trim":
                        sell_volume_unnecessary += fill.quantity

            inventory_rows.append(
                {
                    "index": index,
                    "timestamp": tick.timestamp,
                    "progress": progress,
                    "mid_price": mid,
                    "position": position,
                    "realized_pnl": realized_pnl,
                    "target_pos": int(info.get("target_pos", 0)),
                    "pullback": float(info.get("pullback", 0.0)),
                    "gap": int(info.get("gap", 0)),
                }
            )

        last_mid = float(ticks[-1].products[self.product].mid_price or 0.0)
        unrealized_pnl = position * last_mid
        final_equity = realized_pnl + unrealized_pnl
        capture_pnl = sum(pnl_capture_terms)
        ideal_capture = sum(ideal_capture_terms)
        trend_capture_ratio = capture_pnl / ideal_capture if ideal_capture > 0 else 0.0

        positions = [row["position"] for row in inventory_rows]
        progress_cut = lambda p: [row["position"] for row in inventory_rows if row["progress"] <= p]
        after_cut = lambda p: [row["position"] for row in inventory_rows if row["progress"] >= p]

        metrics: Dict[str, float | int | str | None] = {
            "dataset_id": self.dataset.dataset_id,
            "product": self.product,
            "final_equity": round(final_equity, 6),
            "realized_pnl": round(realized_pnl, 6),
            "unrealized_pnl": round(unrealized_pnl, 6),
            "markout_pnl": round(self._markout_pnl(fills, ticks, horizon=20), 6),
            "avg_pos": round(mean(positions), 6) if positions else 0.0,
            "early_pos_5pct": round(mean(progress_cut(0.05)), 6) if progress_cut(0.05) else 0.0,
            "early_pos_10pct": round(mean(progress_cut(0.10)), 6) if progress_cut(0.10) else 0.0,
            "early_pos_20pct": round(mean(progress_cut(0.20)), 6) if progress_cut(0.20) else 0.0,
            "avg_pos_after_20pct": round(mean(after_cut(0.20)), 6) if after_cut(0.20) else 0.0,
            "avg_pos_after_50pct": round(mean(after_cut(0.50)), 6) if after_cut(0.50) else 0.0,
            "final_pos": int(position),
            "max_pos": int(max(positions) if positions else 0),
            "time_above_60": round(sum(1 for p in positions if p >= 60) / max(1, len(positions)), 6),
            "time_above_70": round(sum(1 for p in positions if p >= 70) / max(1, len(positions)), 6),
            "trend_capture_ratio": round(trend_capture_ratio, 6),
            "avg_entry_price_first_10pct": self._entry_price_prefix(buy_prices, int(self.position_limit * 0.10)),
            "avg_entry_price_first_20pct": self._entry_price_prefix(buy_prices, int(self.position_limit * 0.20)),
            "avg_buy_price": self._vwap(buy_prices),
            "avg_pullback_add_price": self._vwap(pullback_add_prices),
            "num_trades": len(fills),
            "num_buy_trades": sum(1 for fill in fills if fill.side == "buy"),
            "num_sell_trades": sum(1 for fill in fills if fill.side == "sell"),
            "passive_fill_rate": round(passive_filled_qty / passive_posted_qty, 6) if passive_posted_qty else 0.0,
            "taker_fraction": round(taker_filled_qty / max(1, taker_filled_qty + passive_filled_qty), 6),
            "inventory_retention_rate": round((mean(after_cut(0.20)) if after_cut(0.20) else 0.0) / max(1.0, (mean(progress_cut(0.20)) if progress_cut(0.20) else 0.0)), 6),
            "unnecessary_sell_ratio": round(sell_volume_unnecessary / sell_volume_total, 6) if sell_volume_total else 0.0,
            "num_pullback_adds": len(pullback_events),
            "avg_pullback_depth_at_add": round(mean([evt["pullback"] for evt in pullback_events]), 6) if pullback_events else 0.0,
            "post_add_return_20ticks": round(self._post_add_return(pullback_events, ticks, 20), 6),
            "post_add_return_50ticks": round(self._post_add_return(pullback_events, ticks, 50), 6),
            "replenishment_rate": round(replenishment_filled / replenishment_posted, 6) if replenishment_posted else 0.0,
        }

        artifacts = None
        if out_dir is not None:
            out_dir.mkdir(parents=True, exist_ok=True)
            summary_path = out_dir / "pepper_summary.json"
            fills_path = out_dir / "pepper_fills.json"
            inventory_path = out_dir / "pepper_inventory.csv"
            metrics_path = out_dir / "pepper_metrics.json"
            summary_path.write_text(
                json.dumps({"config": self.config.to_dict(), "metrics": metrics}, indent=2),
                encoding="utf-8",
            )
            fills_path.write_text(
                json.dumps([asdict(fill) for fill in fills], indent=2),
                encoding="utf-8",
            )
            inventory_header = "index,timestamp,progress,mid_price,position,realized_pnl,target_pos,pullback,gap"
            inventory_lines = [inventory_header]
            for row in inventory_rows:
                inventory_lines.append(
                    ",".join(
                        [
                            str(row["index"]),
                            str(row["timestamp"]),
                            f"{row['progress']:.6f}",
                            f"{row['mid_price']:.6f}",
                            str(row["position"]),
                            f"{row['realized_pnl']:.6f}",
                            str(row["target_pos"]),
                            f"{row['pullback']:.6f}",
                            str(row["gap"]),
                        ]
                    )
                )
            inventory_path.write_text("\n".join(inventory_lines) + "\n", encoding="utf-8")
            metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
            artifacts = PepperRunArtifacts(
                summary_path=summary_path,
                fills_path=fills_path,
                inventory_path=inventory_path,
                metrics_path=metrics_path,
            )

        return PepperRunResult(config=self.config, metrics=metrics, fills=fills, artifacts=artifacts)

    def _execute_tick(
        self,
        index: int,
        tick: TickSnapshot,
        intents: List[PepperOrderIntent],
        progress: float,
        pullback: float,
        mid_price: float,
    ) -> List[PepperFillEvent]:
        snapshot = tick.products[self.product]
        bids = [[level.price, level.volume] for level in snapshot.bids]
        asks = [[level.price, level.volume] for level in snapshot.asks]
        market_trades = list(tick.market_trades.get(self.product, []))
        fills: List[PepperFillEvent] = []

        for intent in intents:
            if intent.quantity > 0:
                remaining = intent.quantity
                crossed = False
                if intent.style == "taker" or (asks and intent.price >= asks[0][0]):
                    crossed = True
                    for level in asks:
                        if remaining <= 0:
                            break
                        price, volume = level
                        if volume <= 0 or price > intent.price:
                            continue
                        fill_qty = min(remaining, volume)
                        fills.append(self._fill_event(tick, index, intent, fill_qty, "buy", progress, mid_price, pullback, price))
                        remaining -= fill_qty
                        level[1] -= fill_qty
                if remaining > 0 and intent.style == "passive" and not crossed:
                    available = sum(
                        trade.quantity for trade in market_trades
                        if trade.quantity > 0 and trade.price <= intent.price
                    )
                    fill_cap = int(round(available * self.config.passive_fill_ratio))
                    fill_qty = min(remaining, fill_cap)
                    if fill_qty > 0:
                        fills.append(self._fill_event(tick, index, intent, fill_qty, "buy", progress, mid_price, pullback, intent.price))
                        self._consume_market(market_trades, fill_qty, lambda trade: trade.price <= intent.price)
            elif intent.quantity < 0:
                remaining = -intent.quantity
                crossed = False
                if intent.style == "taker" or (bids and intent.price <= bids[0][0]):
                    crossed = True
                    for level in bids:
                        if remaining <= 0:
                            break
                        price, volume = level
                        if volume <= 0 or price < intent.price:
                            continue
                        fill_qty = min(remaining, volume)
                        fills.append(self._fill_event(tick, index, intent, fill_qty, "sell", progress, mid_price, pullback, price))
                        remaining -= fill_qty
                        level[1] -= fill_qty
                if remaining > 0 and intent.style == "passive" and not crossed:
                    available = sum(
                        trade.quantity for trade in market_trades
                        if trade.quantity > 0 and trade.price >= intent.price
                    )
                    fill_cap = int(round(available * self.config.passive_fill_ratio))
                    fill_qty = min(remaining, fill_cap)
                    if fill_qty > 0:
                        fills.append(self._fill_event(tick, index, intent, fill_qty, "sell", progress, mid_price, pullback, intent.price))
                        self._consume_market(market_trades, fill_qty, lambda trade: trade.price >= intent.price)
        return fills

    def _consume_market(self, trades, quantity: int, predicate) -> None:
        remaining = quantity
        for trade in trades:
            if remaining <= 0:
                break
            if trade.quantity <= 0 or not predicate(trade):
                continue
            used = min(remaining, trade.quantity)
            trade.quantity -= used
            remaining -= used

    def _fill_event(
        self,
        tick: TickSnapshot,
        index: int,
        intent: PepperOrderIntent,
        quantity: int,
        side: str,
        progress: float,
        mid_price: float,
        pullback: float,
        execution_price: int,
    ) -> PepperFillEvent:
        return PepperFillEvent(
            timestamp=tick.timestamp,
            index=index,
            symbol=intent.symbol,
            price=execution_price,
            quantity=quantity,
            side=side,
            style=intent.style,
            reason=intent.reason,
            level=intent.level,
            progress=progress,
            mid_price=mid_price,
            pullback=pullback,
        )

    def _vwap(self, rows: List[tuple[int, int]]) -> float:
        total_qty = sum(qty for _, qty in rows)
        if total_qty <= 0:
            return 0.0
        return round(sum(price * qty for price, qty in rows) / total_qty, 6)

    def _entry_price_prefix(self, rows: List[tuple[int, int]], target_qty: int) -> float:
        if target_qty <= 0:
            return 0.0
        remaining = target_qty
        used: List[tuple[int, int]] = []
        for price, qty in rows:
            if remaining <= 0:
                break
            take = min(remaining, qty)
            used.append((price, take))
            remaining -= take
        return self._vwap(used)

    def _post_add_return(self, events: List[dict], ticks: List[TickSnapshot], horizon: int) -> float:
        if not events:
            return 0.0
        returns = []
        for evt in events:
            end_index = min(len(ticks) - 1, evt["index"] + horizon)
            future_mid = float(ticks[end_index].products[self.product].mid_price or 0.0)
            returns.append(future_mid - evt["price"])
        return mean(returns) if returns else 0.0

    def _markout_pnl(self, fills: List[PepperFillEvent], ticks: List[TickSnapshot], horizon: int) -> float:
        if not fills:
            return 0.0
        markouts = []
        for fill in fills:
            end_index = min(len(ticks) - 1, fill.index + horizon)
            future_mid = float(ticks[end_index].products[self.product].mid_price or 0.0)
            if fill.side == "buy":
                markouts.append((future_mid - fill.price) * fill.quantity)
            else:
                markouts.append((fill.price - future_mid) * fill.quantity)
        return sum(markouts)
