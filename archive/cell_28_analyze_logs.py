
def analyze_log_files(backtest_dir):
    log_files = [f for f in os.listdir(backtest_dir) if f.endswith('.log')]
    
    results = []
    for log_file in log_files:
        file_path = os.path.join(backtest_dir, log_file)
        
        # Extract symbol and parameters from the file name
        file_name = os.path.splitext(log_file)[0]
        print(file_name)
        symbol, params_str = file_name.split('-', 1)
        params = dict(param.split('=') for param in params_str.split('-'))
        
        # Read the contents of the log file
        with open(file_path, 'r') as file:
            log_content = file.read()
        
        # Store the symbol, parameters, and log content in the results
        results.append({
            'symbol': symbol,
            'params': params,
            'log_content': log_content
        })
    
    return results

# Analyze the log files
log_analysis_results = analyze_log_files(backtest_dir)

# Print the results
for result in log_analysis_results:
    print(f"Symbol: {result['symbol']}")
    print(f"Parameters: {result['params']}")
#     print(f"Log Content:\n{result['log_content']}\n")