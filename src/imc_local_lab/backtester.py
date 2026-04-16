from __future__ import annotations

import json
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .datamodel import (
    ConversionObservation,
    Listing,
    Observation,
    Order,
    OrderDepth,
    ProsperityEncoder,
    Trade,
    TradingState,
)
from .dataset import (
    BacktestArtifacts,
    BacktestSummary,
    MarketTradeRow,
    NormalizedDataset,
    ProductSnapshot,
    TickSnapshot,
)

DEFAULT_LIMITS: Dict[str, int] = {
    "EMERALDS": 80,
    "TOMATOES": 80,
    "INTARIAN_PEPPER_ROOT": 80,
    "ASH_COATED_OSMIUM": 80,
    "RAINFOREST_RESIN": 50,
    "KELP": 50,
    "SQUID_INK": 50,
    "CROISSANTS": 250,
    "JAMS": 350,
    "DJEMBES": 60,
    "PICNIC_BASKET1": 60,
    "PICNIC_BASKET2": 100,
    "VOLCANIC_ROCK": 400,
    "VOLCANIC_ROCK_VOUCHER_9500": 200,
    "VOLCANIC_ROCK_VOUCHER_9750": 200,
    "VOLCANIC_ROCK_VOUCHER_10000": 200,
    "VOLCANIC_ROCK_VOUCHER_10250": 200,
    "VOLCANIC_ROCK_VOUCHER_10500": 200,
    "MAGNIFICENT_MACARONS": 75,
}


class Backtester:
    def __init__(
        self,
        dataset: NormalizedDataset,
        position_limits: Optional[Dict[str, int]] = None,
        trade_match_mode: str = "all",
    ):
        self.dataset = dataset
        self.position_limits = {**DEFAULT_LIMITS, **(position_limits or {})}
        self.trade_match_mode = trade_match_mode

    def run(self, trader, out_dir: Path) -> BacktestSummary:
        out_dir.mkdir(parents=True, exist_ok=True)

        trader_data = ""
        position: Dict[str, int] = defaultdict(int)
        cash: Dict[str, float] = defaultdict(float)
        own_trades_prev: Dict[str, List[Trade]] = defaultdict(list)
        market_trades_prev: Dict[str, List[Trade]] = defaultdict(list)

        sandbox_logs: List[dict] = []
        trade_history: List[dict] = []
        activity_header = (
            "day;timestamp;product;bid_price_1;bid_volume_1;bid_price_2;bid_volume_2;"
            "bid_price_3;bid_volume_3;ask_price_1;ask_volume_1;ask_price_2;ask_volume_2;"
            "ask_price_3;ask_volume_3;mid_price;profit_and_loss"
        )
        activity_lines = [activity_header]

        for tick in self.dataset.ticks:
            state = self._build_state(
                tick=tick,
                trader_data=trader_data,
                position=position,
                own_trades=own_trades_prev,
                market_trades=market_trades_prev,
            )
            result = trader.run(state)
            orders, conversions, trader_data = self._normalize_run_output(result)
            self._type_check_orders(orders)
            filtered_orders, limit_messages = self._enforce_limits(position, orders)
            new_own_trades, new_market_trades = self._match_tick(
                tick=tick,
                orders=filtered_orders,
                position=position,
                cash=cash,
            )

            sandbox_logs.append(
                {
                    "timestamp": tick.timestamp,
                    "sandboxLog": "\n".join(limit_messages).strip(),
                    "lambdaLog": "",
                    "conversions": conversions,
                }
            )

            own_trades_prev = defaultdict(list, new_own_trades)
            market_trades_prev = defaultdict(list, new_market_trades)

            trade_history.extend(self._trade_dicts_from_map(new_market_trades, tick.day))
            trade_history.extend(self._trade_dicts_from_map(new_own_trades, tick.day))
            activity_lines.extend(self._activity_lines_for_tick(tick, position, cash))

        final_pnl_by_product = self._final_pnl_map(position, cash, self.dataset.ticks[-1])
        final_pnl_total = sum(final_pnl_by_product.values())

        submission_log_path = out_dir / "submission.log"
        activities_csv_path = out_dir / "activities.csv"
        sandbox_logs_path = out_dir / "sandbox_logs.json"
        trade_history_path = out_dir / "trade_history.json"
        metrics_path = out_dir / "metrics.json"

        submission_payload = {
            "submissionId": str(uuid.uuid4()),
            "activitiesLog": "\n".join(activity_lines),
            "logs": sandbox_logs,
            "tradeHistory": trade_history,
        }
        submission_log_path.write_text(
            json.dumps(submission_payload, cls=ProsperityEncoder, indent=2),
            encoding="utf-8",
        )
        activities_csv_path.write_text("\n".join(activity_lines) + "\n", encoding="utf-8")
        sandbox_logs_path.write_text(json.dumps(sandbox_logs, indent=2), encoding="utf-8")
        trade_history_path.write_text(json.dumps(trade_history, indent=2), encoding="utf-8")
        metrics_path.write_text(
            json.dumps(
                {
                    "dataset_id": self.dataset.dataset_id,
                    "tick_count": len(self.dataset.ticks),
                    "final_pnl_total": final_pnl_total,
                    "final_pnl_by_product": final_pnl_by_product,
                    "trade_match_mode": self.trade_match_mode,
                    "conversions_note": "Conversions are recorded from trader output but not executed in this local engine.",
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        return BacktestSummary(
            dataset_id=self.dataset.dataset_id,
            tick_count=len(self.dataset.ticks),
            final_pnl_total=final_pnl_total,
            final_pnl_by_product=final_pnl_by_product,
            artifacts=BacktestArtifacts(
                metrics_path=metrics_path,
                submission_log_path=submission_log_path,
                activities_csv_path=activities_csv_path,
                sandbox_logs_path=sandbox_logs_path,
                trade_history_path=trade_history_path,
            ),
        )

    def _build_state(
        self,
        tick: TickSnapshot,
        trader_data: str,
        position: Dict[str, int],
        own_trades: Dict[str, List[Trade]],
        market_trades: Dict[str, List[Trade]],
    ) -> TradingState:
        listings = {
            product: Listing(symbol=product, product=product, denomination="SEASHELLS")
            for product in tick.products
        }
        order_depths = {
            product: self._to_order_depth(snapshot)
            for product, snapshot in tick.products.items()
        }
        observation = self._to_observation(tick)
        return TradingState(
            traderData=trader_data,
            timestamp=tick.timestamp,
            listings=listings,
            order_depths=order_depths,
            own_trades={product: list(rows) for product, rows in own_trades.items()},
            market_trades={product: list(rows) for product, rows in market_trades.items()},
            position=dict(position),
            observations=observation,
        )

    def _to_order_depth(self, snapshot: ProductSnapshot) -> OrderDepth:
        depth = OrderDepth()
        for level in snapshot.bids:
            depth.buy_orders[level.price] = level.volume
        for level in snapshot.asks:
            depth.sell_orders[level.price] = -level.volume
        return depth

    def _to_observation(self, tick: TickSnapshot) -> Observation:
        conversion = {}
        for product, values in tick.observations.conversion.items():
            conversion[product] = ConversionObservation(
                bidPrice=float(values.get("bidPrice", 0.0)),
                askPrice=float(values.get("askPrice", 0.0)),
                transportFees=float(values.get("transportFees", 0.0)),
                exportTariff=float(values.get("exportTariff", 0.0)),
                importTariff=float(values.get("importTariff", 0.0)),
                sugarPrice=float(values.get("sugarPrice", 0.0)),
                sunlightIndex=float(values.get("sunlightIndex", 0.0)),
            )
        return Observation(
            plainValueObservations=dict(tick.observations.plain),
            conversionObservations=conversion,
        )

    def _normalize_run_output(self, result) -> Tuple[Dict[str, List[Order]], int, str]:
        if isinstance(result, tuple):
            if len(result) == 3:
                orders, conversions, trader_data = result
            elif len(result) == 2:
                orders, trader_data = result
                conversions = 0
            elif len(result) == 1:
                orders = result[0]
                conversions = 0
                trader_data = ""
            else:
                raise ValueError("Trader.run returned an unsupported tuple length")
        else:
            orders = result
            conversions = 0
            trader_data = ""
        return orders or {}, int(conversions), str(trader_data)

    def _type_check_orders(self, orders: Dict[str, List[Order]]) -> None:
        if not isinstance(orders, dict):
            raise TypeError("orders must be a dict[str, list[Order]]")
        for symbol, rows in orders.items():
            if not isinstance(symbol, str):
                raise TypeError("order book keys must be strings")
            if not isinstance(rows, list):
                raise TypeError(f"orders for {symbol} must be a list")
            for order in rows:
                if not isinstance(order, Order):
                    raise TypeError(f"{symbol} contains a non-Order instance")
                if not isinstance(order.price, int) or not isinstance(order.quantity, int):
                    raise TypeError("order.price and order.quantity must be integers")

    def _enforce_limits(
        self,
        position: Dict[str, int],
        orders: Dict[str, List[Order]],
    ) -> Tuple[Dict[str, List[Order]], List[str]]:
        filtered: Dict[str, List[Order]] = {}
        messages: List[str] = []
        for product, rows in orders.items():
            limit = self.position_limits.get(product, 100)
            current = position.get(product, 0)
            long_total = sum(max(0, order.quantity) for order in rows)
            short_total = sum(max(0, -order.quantity) for order in rows)
            if current + long_total > limit or current - short_total < -limit:
                messages.append(
                    f"Orders for product {product} exceeded limit of {limit} and were removed for this tick"
                )
                continue
            filtered[product] = rows
        return filtered, messages

    def _match_tick(
        self,
        tick: TickSnapshot,
        orders: Dict[str, List[Order]],
        position: Dict[str, int],
        cash: Dict[str, float],
    ) -> Tuple[Dict[str, List[Trade]], Dict[str, List[Trade]]]:
        own_trades_out: Dict[str, List[Trade]] = defaultdict(list)
        market_trades_out: Dict[str, List[Trade]] = defaultdict(list)

        for product, snapshot in tick.products.items():
            bids = [[level.price, level.volume] for level in snapshot.bids]
            asks = [[level.price, level.volume] for level in snapshot.asks]
            remaining_market = [
                Trade(
                    symbol=trade.symbol,
                    price=trade.price,
                    quantity=trade.quantity,
                    buyer=trade.buyer,
                    seller=trade.seller,
                    timestamp=trade.timestamp,
                )
                for trade in tick.market_trades.get(product, [])
            ]

            for order in orders.get(product, []):
                own_trades = self._match_single_order(
                    order=Order(order.symbol, order.price, order.quantity),
                    product=product,
                    bids=bids,
                    asks=asks,
                    market_trades=remaining_market,
                    position=position,
                    cash=cash,
                    timestamp=tick.timestamp,
                )
                own_trades_out[product].extend(own_trades)

            market_trades_out[product] = [trade for trade in remaining_market if trade.quantity > 0]

        return own_trades_out, market_trades_out

    def _match_single_order(
        self,
        order: Order,
        product: str,
        bids: List[List[int]],
        asks: List[List[int]],
        market_trades: List[Trade],
        position: Dict[str, int],
        cash: Dict[str, float],
        timestamp: int,
    ) -> List[Trade]:
        fills: List[Trade] = []

        if order.quantity > 0:
            for level in asks:
                if order.quantity <= 0:
                    break
                price, volume = level
                if volume <= 0 or price > order.price:
                    continue
                fill_qty = min(order.quantity, volume)
                fills.append(Trade(product, price, fill_qty, "SUBMISSION", "", timestamp))
                position[product] += fill_qty
                cash[product] -= price * fill_qty
                level[1] -= fill_qty
                order.quantity -= fill_qty

            if order.quantity > 0 and self.trade_match_mode != "none":
                for trade in market_trades:
                    if order.quantity <= 0:
                        break
                    if trade.quantity <= 0:
                        continue
                    if not self._trade_price_is_eligible(order.price, trade.price, is_buy=True):
                        continue
                    fill_qty = min(order.quantity, trade.quantity)
                    fills.append(Trade(product, order.price, fill_qty, "SUBMISSION", trade.seller, timestamp))
                    position[product] += fill_qty
                    cash[product] -= order.price * fill_qty
                    order.quantity -= fill_qty
                    trade.quantity -= fill_qty
        elif order.quantity < 0:
            remaining_to_sell = -order.quantity
            for level in bids:
                if remaining_to_sell <= 0:
                    break
                price, volume = level
                if volume <= 0 or price < order.price:
                    continue
                fill_qty = min(remaining_to_sell, volume)
                fills.append(Trade(product, price, fill_qty, "", "SUBMISSION", timestamp))
                position[product] -= fill_qty
                cash[product] += price * fill_qty
                level[1] -= fill_qty
                remaining_to_sell -= fill_qty

            if remaining_to_sell > 0 and self.trade_match_mode != "none":
                for trade in market_trades:
                    if remaining_to_sell <= 0:
                        break
                    if trade.quantity <= 0:
                        continue
                    if not self._trade_price_is_eligible(order.price, trade.price, is_buy=False):
                        continue
                    fill_qty = min(remaining_to_sell, trade.quantity)
                    fills.append(Trade(product, order.price, fill_qty, trade.buyer, "SUBMISSION", timestamp))
                    position[product] -= fill_qty
                    cash[product] += order.price * fill_qty
                    remaining_to_sell -= fill_qty
                    trade.quantity -= fill_qty

        return fills

    def _trade_price_is_eligible(self, order_price: int, trade_price: int, is_buy: bool) -> bool:
        if self.trade_match_mode == "all":
            return trade_price <= order_price if is_buy else trade_price >= order_price
        if self.trade_match_mode == "worse":
            return trade_price < order_price if is_buy else trade_price > order_price
        return False

    def _activity_lines_for_tick(
        self,
        tick: TickSnapshot,
        position: Dict[str, int],
        cash: Dict[str, float],
    ) -> List[str]:
        lines: List[str] = []
        pnl_map = self._final_pnl_map(position, cash, tick)
        for product, snapshot in sorted(tick.products.items()):
            bids = snapshot.bids
            asks = snapshot.asks
            line = [
                "" if tick.day is None else str(tick.day),
                str(tick.timestamp),
                product,
                str(bids[0].price) if len(bids) > 0 else "",
                str(bids[0].volume) if len(bids) > 0 else "",
                str(bids[1].price) if len(bids) > 1 else "",
                str(bids[1].volume) if len(bids) > 1 else "",
                str(bids[2].price) if len(bids) > 2 else "",
                str(bids[2].volume) if len(bids) > 2 else "",
                str(asks[0].price) if len(asks) > 0 else "",
                str(asks[0].volume) if len(asks) > 0 else "",
                str(asks[1].price) if len(asks) > 1 else "",
                str(asks[1].volume) if len(asks) > 1 else "",
                str(asks[2].price) if len(asks) > 2 else "",
                str(asks[2].volume) if len(asks) > 2 else "",
                "" if snapshot.mid_price is None else str(snapshot.mid_price),
                str(round(pnl_map.get(product, 0.0), 6)),
            ]
            lines.append(";".join(line))
        return lines

    def _final_pnl_map(
        self,
        position: Dict[str, int],
        cash: Dict[str, float],
        tick: TickSnapshot,
    ) -> Dict[str, float]:
        pnl: Dict[str, float] = {}
        for product, snapshot in tick.products.items():
            mark = snapshot.mid_price or 0.0
            pnl[product] = cash.get(product, 0.0) + position.get(product, 0) * mark
        return pnl

    def _trade_dicts_from_map(self, rows: Dict[str, List[Trade]], day: Optional[int]) -> List[dict]:
        out: List[dict] = []
        for trades in rows.values():
            for trade in trades:
                out.append(
                    {
                        "day": day,
                        "timestamp": trade.timestamp,
                        "buyer": trade.buyer or "",
                        "seller": trade.seller or "",
                        "symbol": trade.symbol,
                        "currency": "SEASHELLS",
                        "price": trade.price,
                        "quantity": trade.quantity,
                    }
                )
        return out
