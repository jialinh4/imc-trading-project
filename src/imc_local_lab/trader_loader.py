from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from . import datamodel


class TraderLoadError(RuntimeError):
    pass


def load_trader_module(trader_path: Path) -> ModuleType:
    module_name = f"user_trader_{trader_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, trader_path)
    if spec is None or spec.loader is None:
        raise TraderLoadError(f"Cannot load trader file: {trader_path}")

    module = importlib.util.module_from_spec(spec)
    previous_datamodel = sys.modules.get("datamodel")
    previous_module = sys.modules.get(module_name)
    sys.modules["datamodel"] = datamodel
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        if previous_datamodel is None:
            sys.modules.pop("datamodel", None)
        else:
            sys.modules["datamodel"] = previous_datamodel
        if previous_module is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous_module
    return module


def load_trader_instance(trader_path: Path) -> Any:
    module = load_trader_module(trader_path)
    trader_class = getattr(module, "Trader", None)
    if trader_class is None:
        raise TraderLoadError(f"Trader file does not expose a Trader class: {trader_path}")
    return trader_class()
