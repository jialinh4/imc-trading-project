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
