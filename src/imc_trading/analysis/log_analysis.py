import os


def analyze_log_files(backtest_dir):
    log_files = [f for f in os.listdir(backtest_dir) if f.endswith(".log")]

    results = []
    for log_file in log_files:
        file_path = os.path.join(backtest_dir, log_file)

        file_name = os.path.splitext(log_file)[0]
        symbol, params_str = file_name.split("-", 1)
        params = dict(param.split("=") for param in params_str.split("-"))

        with open(file_path, "r", encoding="utf-8") as file:
            log_content = file.read()

        results.append(
            {
                "symbol": symbol,
                "params": params,
                "log_content": log_content,
            }
        )

    return results
