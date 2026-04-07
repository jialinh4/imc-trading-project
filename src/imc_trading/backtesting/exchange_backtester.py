from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Dict, Iterable, List

import pandas as pd
from datamodel import Listing, Observation, Order, OrderDepth, Trade, TradingState

from .accounting import AccountingEngine
from .matching import Fill, MakerMatcher, TakerMatcher
from .order_manager import ManagedOrder, OrderManager, Side, TimeInForce
from .queue_tracker import QueueModel, QueueTracker


class ExchangeBacktester:
    """
    Phase 3 exchange-style backtester.

    Included in this phase:
    - queue-aware maker matching for resting passive orders
    - price-priority then FIFO matching across multiple resting orders
    - queue_model='simple' as the default passive fill model
    - 'none' compatibility mode remains available for comparison

    Deferred to later phases:
    - pro-rata queue model
    - full accounting/log output migration
    """

    def __init__(
        self,
        trader,
        listings: Dict[str, Listing],
        position_limit: Dict[str, int],
        fair_marks,
        market_data: pd.DataFrame,
        trade_history: pd.DataFrame,
        file_name: str | None = None,
        resting_mode: str = "cancel_replace",
        default_tif: TimeInForce = TimeInForce.GFD,
        queue_model: str = "simple",
    ):
        self.trader = trader
        self.listings = listings
        self.position_limit = position_limit
        self.fair_marks = fair_marks
        self.market_data = market_data
        self.trade_history = trade_history.sort_values(by=["timestamp", "symbol"])
        self.file_name = file_name
        self.resting_mode = resting_mode
        self.default_tif = default_tif
        self.queue_model = QueueModel(queue_model).value

        self.observations = [Observation({}, {}) for _ in range(len(market_data))]
        self.queue_tracker = QueueTracker()
        self.order_manager = OrderManager(queue_tracker=self.queue_tracker)
        self.taker_matcher = TakerMatcher(self.order_manager)
        self.maker_matcher = MakerMatcher(self.order_manager, queue_tracker=self.queue_tracker)
        self.accounting = AccountingEngine()

        self.current_position = {product: 0 for product in self.listings.keys()}
        self.pnl_history: List[float] = []
        self.pnl = {product: 0.0 for product in self.listings.keys()}
        self.cash = {product: 0.0 for product in self.listings.keys()}
        self.trades: List[Dict[str, Any]] = []
        self.sandbox_logs: List[Dict[str, Any]] = []

    def run(self):
        trader_data = ""
        timestamp_group_md = self.market_data.groupby("timestamp")
        timestamp_group_th = self.trade_history.groupby("timestamp")
        trade_history_dict = self._build_trade_history_dict(timestamp_group_th)

        pending_own_trades: Dict[str, List[Trade]] = defaultdict(list)

        for timestamp, group in timestamp_group_md:
            order_depths = self._construct_order_depths(group)
            order_depths_matching = self._construct_order_depths(group)
            sandbox_log = ""

            market_trades_now = trade_history_dict.get(int(timestamp), [])
            market_trades_for_state: Dict[str, List[Trade]] = defaultdict(list)
            for trade in market_trades_now:
                market_trades_for_state[trade.symbol].append(trade)

            resting_fills_at_timestamp = self._match_resting_orders(timestamp, market_trades_now)
            for product, fills in resting_fills_at_timestamp.items():
                pending_own_trades[product].extend(
                    [self._fill_to_trade(fill, self.order_manager.orders[fill.order_id], timestamp) for fill in fills]
                )

            state = self._construct_trading_state(
                trader_data,
                timestamp,
                self.listings,
                order_depths,
                dict(pending_own_trades),
                dict(market_trades_for_state),
                dict(self.current_position),
                self.observations,
            )
            pending_own_trades = defaultdict(list)

            orders, conversions, trader_data = self.trader.run(state)
            _ = conversions

            if self.resting_mode == "cancel_replace":
                for product in group["product"].tolist():
                    self.order_manager.cancel_symbol_orders(product, timestamp)

            fills_at_timestamp: Dict[str, List[Fill]] = defaultdict(list)
            for product, fills in resting_fills_at_timestamp.items():
                fills_at_timestamp[product].extend(fills)

            raw_orders = self._normalize_orders(orders)
            for product, product_orders in raw_orders.items():
                order_depth = order_depths_matching[product]
                for raw_order in product_orders:
                    managed = self.order_manager.submit_raw_order(
                        raw_order,
                        ts=timestamp,
                        order_depth=order_depth,
                        tif=self.default_tif,
                    )
                    if managed.is_aggressive:
                        fills = self._match_aggressive_order(
                            managed,
                            order_depth,
                            timestamp,
                            sandbox_log,
                        )
                        fills_at_timestamp[product].extend(fills)
                        pending_own_trades[product].extend(
                            [self._fill_to_trade(fill, self.order_manager.orders[fill.order_id], timestamp) for fill in fills]
                        )
                    if managed.tif == TimeInForce.IOC and managed.remaining_qty > 0:
                        self.order_manager.cancel(managed.order_id, timestamp)

            self._append_trades(
                own_trades=self._convert_fills_to_trade_dict(fills_at_timestamp),
                market_trades=dict(market_trades_for_state),
            )

            current_order_depths = self._construct_order_depths(group)
            for product in group["product"].tolist():
                fair_value = self._compute_fair_value(product, timestamp, group)
                snapshot = self.accounting.mark(
                    timestamp=timestamp,
                    symbol=product,
                    order_depth=current_order_depths[product],
                    fair_value=fair_value,
                    num_fills=len(fills_at_timestamp.get(product, [])),
                )
                self.current_position[product] = self.accounting.position.get(product, 0)
                self.cash[product] = self.accounting.cash.get(product, 0.0)
                self.pnl[product] = snapshot.total_pnl_fair
                self.pnl_history.append(snapshot.total_pnl_fair)

            self.sandbox_logs.append({"sandboxLog": sandbox_log, "lambdaLog": "", "timestamp": timestamp})

        if len(self.market_data) > 0:
            last_ts = int(self.market_data["timestamp"].max())
            self.order_manager.expire_all(last_ts)
        return self._log_trades(self.file_name)

    def _build_trade_history_dict(self, timestamp_groups: Iterable[tuple[int, pd.DataFrame]]) -> Dict[int, List[Trade]]:
        trade_history_dict: Dict[int, List[Trade]] = {}
        for timestamp, group in timestamp_groups:
            trades = []
            for _, row in group.iterrows():
                trades.append(
                    Trade(
                        row["symbol"],
                        int(row["price"]),
                        int(row["quantity"]),
                        row["buyer"] if pd.notnull(row["buyer"]) else "",
                        row["seller"] if pd.notnull(row["seller"]) else "",
                        timestamp,
                    )
                )
            trade_history_dict[int(timestamp)] = trades
        return trade_history_dict

    def _normalize_orders(self, orders: Any) -> Dict[str, List[Order]]:
        if isinstance(orders, dict):
            return {symbol: list(symbol_orders) for symbol, symbol_orders in orders.items()}
        raise TypeError("Trader.run() must return a dict[str, list[Order]] as first value.")

    def _match_resting_orders(self, timestamp: int, trade_flow: List[Trade]) -> Dict[str, List[Fill]]:
        fills_by_symbol: Dict[str, List[Fill]] = defaultdict(list)
        if not trade_flow:
            return fills_by_symbol

        symbols = sorted({trade.symbol for trade in trade_flow})
        for symbol in symbols:
            symbol_trade_flow = [trade for trade in trade_flow if trade.symbol == symbol]
            for side in (Side.BUY, Side.SELL):
                for orders_at_price in self.order_manager.get_resting_price_levels(side=side, symbol=symbol):
                    fills = self.maker_matcher.match_resting_orders(
                        orders_at_price,
                        symbol_trade_flow,
                        timestamp,
                        queue_model=self.queue_model,
                    )
                    for fill in fills:
                        managed = self.order_manager.orders[fill.order_id]
                        signed_qty = fill.fill_qty if managed.side == Side.BUY else -fill.fill_qty
                        self.accounting.record_fill(fill, signed_qty=signed_qty)
                        self.current_position[fill.symbol] = self.accounting.position.get(fill.symbol, 0)
                        fills_by_symbol[fill.symbol].append(fill)
        return fills_by_symbol

    def _match_aggressive_order(
        self,
        managed: ManagedOrder,
        order_depth: OrderDepth,
        timestamp: int,
        sandbox_log: str,
    ) -> List[Fill]:
        fills = self.taker_matcher.match(managed, order_depth, timestamp)
        accepted_fills: List[Fill] = []
        for fill in fills:
            signed_qty = fill.fill_qty if managed.side == Side.BUY else -fill.fill_qty
            projected_position = self.current_position.get(fill.symbol, 0) + signed_qty
            limit = int(self.position_limit[fill.symbol])
            if abs(projected_position) > limit:
                sandbox_log += f"\nOrders for product {fill.symbol} exceeded limit of {limit} set"
                self.order_manager.cancel(managed.order_id, timestamp)
                break
            self.accounting.record_fill(fill, signed_qty=signed_qty)
            self.current_position[fill.symbol] = self.accounting.position.get(fill.symbol, 0)
            accepted_fills.append(fill)
        return accepted_fills

    def _convert_fills_to_trade_dict(self, fills_by_symbol: Dict[str, List[Fill]]) -> Dict[str, List[Trade]]:
        converted: Dict[str, List[Trade]] = defaultdict(list)
        for product, fills in fills_by_symbol.items():
            for fill in fills:
                managed = self.order_manager.orders[fill.order_id]
                converted[product].append(self._fill_to_trade(fill, managed, fill.timestamp))
        return converted

    def _fill_to_trade(self, fill: Fill, managed: ManagedOrder, timestamp: int) -> Trade:
        if managed.side == Side.BUY:
            return Trade(fill.symbol, int(fill.fill_price), int(fill.fill_qty), "SUBMISSION", "", timestamp)
        return Trade(fill.symbol, int(fill.fill_price), int(fill.fill_qty), "", "SUBMISSION", timestamp)

    def _compute_fair_value(self, product: str, timestamp: int, group: pd.DataFrame) -> float:
        calculator = self.fair_marks.get(product)
        if calculator is None:
            depth = self._construct_order_depths(group)[product]
            return (max(depth.buy_orders.keys()) + min(depth.sell_orders.keys())) / 2
        try:
            return float(calculator(timestamp, self.market_data))
        except TypeError:
            return float(calculator(self._construct_order_depths(group)[product], self.market_data))
        except Exception:
            depth = self._construct_order_depths(group)[product]
            return (max(depth.buy_orders.keys()) + min(depth.sell_orders.keys())) / 2

    def _log_trades(self, filename: str | None = None):
        if filename is None:
            return None

        self.market_data = self.market_data.copy()
        self.market_data["profit_and_loss"] = self.pnl_history

        output = ""
        output += "Sandbox logs:\n"
        for item in self.sandbox_logs:
            output += json.dumps(item, indent=2) + "\n"

        output += "\n\n\n\nActivities log:\n"
        market_data_csv = self.market_data.to_csv(index=False, sep=";")
        market_data_csv = market_data_csv.replace("\r\n", "\n")
        output += market_data_csv

        output += "\n\n\n\nTrade History:\n"
        output += json.dumps(self.trades, indent=2)

        with open(filename, "w") as file:
            file.write(output)
        return None

    def _append_trades(self, own_trades: Dict[str, List[Trade]], market_trades: Dict[str, List[Trade]]) -> None:
        products = set(own_trades.keys()) | set(market_trades.keys())
        for product in products:
            self.trades.extend([self._trade_to_dict(trade) for trade in own_trades.get(product, [])])
        for product in products:
            self.trades.extend([self._trade_to_dict(trade) for trade in market_trades.get(product, [])])

    def _trade_to_dict(self, trade: Trade) -> Dict[str, Any]:
        return {
            "timestamp": trade.timestamp,
            "buyer": trade.buyer,
            "seller": trade.seller,
            "symbol": trade.symbol,
            "currency": "SEASHELLS",
            "price": trade.price,
            "quantity": trade.quantity,
        }

    def _construct_trading_state(
        self,
        trader_data: str,
        timestamp: int,
        listings: Dict[str, Listing],
        order_depths: Dict[str, OrderDepth],
        own_trades: Dict[str, List[Trade]],
        market_trades: Dict[str, List[Trade]],
        position: Dict[str, int],
        observations: List[Observation],
    ) -> TradingState:
        return TradingState(
            trader_data,
            timestamp,
            listings,
            order_depths,
            own_trades,
            market_trades,
            position,
            observations,
        )

    def _construct_order_depths(self, group: pd.DataFrame) -> Dict[str, OrderDepth]:
        order_depths = {}
        for _, row in group.iterrows():
            product = row["product"]
            order_depth = OrderDepth()
            for level in range(1, 4):
                bid_price_key = f"bid_price_{level}"
                bid_volume_key = f"bid_volume_{level}"
                ask_price_key = f"ask_price_{level}"
                ask_volume_key = f"ask_volume_{level}"

                if not pd.isna(row[bid_price_key]):
                    order_depth.buy_orders[int(row[bid_price_key])] = int(row[bid_volume_key])
                if not pd.isna(row[ask_price_key]):
                    order_depth.sell_orders[int(row[ask_price_key])] = -int(row[ask_volume_key])
            order_depths[product] = order_depth
        return order_depths
