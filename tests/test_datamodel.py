from __future__ import annotations

from imc_local_lab.datamodel import Listing, Observation, Order, OrderDepth, Trade, TradingState


def test_datamodel_roundtrip_smoke() -> None:
    listing = Listing("EMERALDS", "EMERALDS", "SEASHELLS")
    depth = OrderDepth()
    depth.buy_orders[9998] = 5
    depth.sell_orders[10002] = -5
    state = TradingState(
        traderData="",
        timestamp=0,
        listings={"EMERALDS": listing},
        order_depths={"EMERALDS": depth},
        own_trades={"EMERALDS": [Trade("EMERALDS", 10000, 1, "A", "B", 0)]},
        market_trades={},
        position={"EMERALDS": 1},
        observations=Observation({}, {}),
    )
    payload = state.toJSON()
    assert "EMERALDS" in payload
    assert "timestamp" in payload
    order = Order("EMERALDS", 10000, 1)
    assert order.symbol == "EMERALDS"
