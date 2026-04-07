from datamodel import OrderDepth

from imc_trading.backtesting.accounting import AccountingEngine
from imc_trading.backtesting.matching import Fill


def test_accounting_engine_marks_snapshot() -> None:
    engine = AccountingEngine()
    fill = Fill(
        order_id="ord_1",
        symbol="AMETHYSTS",
        fill_price=100,
        fill_qty=3,
        side="taker",
        timestamp=1,
    )

    engine.record_fill(fill, signed_qty=3)

    depth = OrderDepth(buy_orders={99: 10}, sell_orders={101: -10})
    snapshot = engine.mark(
        timestamp=1,
        symbol="AMETHYSTS",
        order_depth=depth,
        fair_value=100,
        num_fills=1,
    )

    assert snapshot.position == 3
    assert snapshot.cash == -300
    assert snapshot.total_pnl_mid == 0
    assert snapshot.total_pnl_fair == 0


def test_accounting_engine_realizes_pnl_when_closing_position() -> None:
    engine = AccountingEngine()
    buy_fill = Fill("ord_1", "AMETHYSTS", 100, 3, "taker", 1)
    sell_fill = Fill("ord_2", "AMETHYSTS", 105, 2, "taker", 2)

    engine.record_fill(buy_fill, signed_qty=3)
    engine.record_fill(sell_fill, signed_qty=-2)

    depth = OrderDepth(buy_orders={104: 10}, sell_orders={106: -10})
    snapshot = engine.mark(2, "AMETHYSTS", depth, fair_value=105, num_fills=1)

    assert snapshot.realized_pnl == 10
    assert snapshot.position == 1
    assert snapshot.cash == -90
