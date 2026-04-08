from datamodel import (
    ConversionObservation,
    Listing,
    Observation,
    Order,
    OrderDepth,
    ProsperityEncoder,
    Trade,
    TradingState,
)


def test_official_datamodel_shapes_and_helpers():
    listing = Listing("STARFRUIT", "STARFRUIT", "SEASHELLS")
    depth = OrderDepth()
    depth.buy_orders[10] = 3
    depth.sell_orders[11] = -2
    conv = ConversionObservation(1.0, 2.0, 0.1, 0.2, 0.3, 5.0, 6.0)
    obs = Observation({"STARFRUIT": 7}, {"ORCHIDS": conv})
    trade = Trade("STARFRUIT", 10, 2, "A", "B", 100)
    state = TradingState(
        traderData="{}",
        timestamp=100,
        listings={"STARFRUIT": listing},
        order_depths={"STARFRUIT": depth},
        own_trades={"STARFRUIT": [trade]},
        market_trades={"STARFRUIT": [trade]},
        position={"STARFRUIT": 1},
        observations=obs,
    )

    assert state.observations is obs
    assert obs.conversionObservations["ORCHIDS"].sunlight == 5.0
    assert obs.conversionObservations["ORCHIDS"].humidity == 6.0
    assert str(Order("STARFRUIT", 10, 1)) == "(STARFRUIT, 10, 1)"
    assert "STARFRUIT" in str(trade)
    assert "order_depths" in state.toJSON()
    assert ProsperityEncoder().default(listing) == listing.__dict__
