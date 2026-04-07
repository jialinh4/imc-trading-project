from imc_trading.analysis.log_analysis import analyze_log_files


def main() -> None:
    results = analyze_log_files("backtests")
    for result in results[:5]:
        print(result["symbol"], result["params"])


if __name__ == "__main__":
    main()
