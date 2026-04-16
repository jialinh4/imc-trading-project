PYTHON ?= python
TRADER ?= examples/sample_trader.py
OUT ?= runs/make_run
ROUND ?= 0
DAY ?=
MATCH ?= all

.PHONY: test tutorial round submission

test:
	$(PYTHON) -m pytest -q

tutorial:
	$(PYTHON) -m imc_local_lab backtest $(TRADER) 0 $(if $(DAY),0-$(DAY),) --data datasets --out $(OUT)/tutorial --trade-match-mode $(MATCH)

round:
	$(PYTHON) -m imc_local_lab backtest $(TRADER) $(ROUND) $(if $(DAY),$(ROUND)-$(DAY),) --data datasets --out $(OUT)/round$(ROUND) --trade-match-mode $(MATCH)

submission:
	$(PYTHON) -m imc_local_lab backtest $(TRADER) $(ROUND)-submission --data datasets --out $(OUT)/submission_round$(ROUND) --trade-match-mode $(MATCH)
