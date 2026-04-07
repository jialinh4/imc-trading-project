from pathlib import Path


def test_expected_modules_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    expected = [
        root / "src" / "imc_trading" / "strategy" / "trader.py",
        root / "src" / "imc_trading" / "backtesting" / "legacy_backtester.py",
        root / "src" / "imc_trading" / "backtesting" / "order_manager.py",
        root / "src" / "imc_trading" / "backtesting" / "matching.py",
        root / "src" / "imc_trading" / "backtesting" / "accounting.py",
    ]
    for path in expected:
        assert path.exists(), f"Missing: {path}"
