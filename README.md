Glider Strat 2

Brief Overview

    This project aims to help backtest strategies on Glider.fi for the "Dynamic" block, which currently does not have a backtest option. 

There are two parts of the project that help accomplish this:

    data_collection/
    data_analysis/  ---> not uploaded in this version

Sample output

    Check SAMPLE ACT-WETH_swap_data.xlsx.
    It represents data collected at Feb 23 8pm AST, 2025 for ACT-WETH, 5 (past) hours of transactions, ~2600. 
    All tx_hash can be double checked on basescan.org/
    -> https://dexscreener.com/base/0x269bda0512de57cd0be0270686ffb3964c05e19b

How to run

    >cd \glider-strat-2\
    >python -m data_collection.transaction_screener

This project aims to support backtesting with a data collection system that interacts with a Uniswap V3-style decentralized exchange on an EVM-compatible blockchain. It fetches raw log data for various token pairs, decodes swap information, and outputs organized CSVs for further analysis.

Table of Contents

    1. Overview
    2. Core Concepts
    3. Project Structure
    4. Dependencies
    5. Configuration Files
    6. Data Flow and Workflow
    7. Key Modules



1. Overview

The data collection module pulls real-time swap information from an on-chain Uniswap V3 pool deployed on Base (an EVM-compatible chain). It uses Alchemy as the RPC provider to query logs, decodes relevant swap events, and computes derived metrics such as price and trade direction (buy/sell). Finally, it aggregates these data points and saves them to CSV for further analysis.

Key Goals:

    Retrieve and store historical swap data for arbitrary Uniswap V3 pools.
    Log buy vs. sell activity for a given “alt token” in each pool.
    Compute the alt token price in terms of a “quote token” (often WETH).
    Output the data in a standardized CSV format suitable for backtesting.

Core Use Cases:

    Generating hourly aggregated metrics like buy/sell counts, average price, and total volume.
    Building a pipeline for ranking multiple tokens based on activity or price changes.
    Serving as the initial data ingestion step for more advanced analyses (e.g. regression, backtests).

2. Core Concepts

2.1 EVM-Compatible Network

The script is primarily tested on Base, a Layer-2 chain that uses the Ethereum Virtual Machine (EVM). However, the methodology applies to any EVM-based network (e.g., Ethereum mainnet, Polygon, Arbitrum) with the same RPC interface.

2.2 Alchemy JSON-RPC

Alchemy provides a high-availability RPC endpoint for reading blockchain data (e.g., logs, block numbers). I supply Alchemy’s URL (e.g., https://base-mainnet.g.alchemy.com/v2/<API_KEY>) in my settings, which the scripts use for all JSON-RPC queries.

Key Methods:

    eth_blockNumber: Gets the latest block on the chain.
    eth_getLogs: Retrieves logs from a specified contract over a block range.
    eth_call: Executes a read-only function on a contract (e.g., token0(), token1()).

2.3 Uniswap V3

A Uniswap V3 pool is a specialized smart contract that manages two tokens (called token0 and token1) and allows swapping between them. It emits a Swap event on every trade, containing:

    amount0 / amount1: The net token amounts swapped.
    sqrtPriceX96: A Q64.96 fixed-point representation of the pool’s price (token1 per token0).

2.4 Price Calculation

In Uniswap V3, sqrtPriceX96 is the square root of (token1 / token0), scaled by 2^96. Squaring it and dividing by 2^192 yields (token1 / token0) as a simple float. Depending on which side the “alt token” occupies (token0 or token1), it auto inverts that ratio to get “quote token per alt token.”

2.5 Buy vs. Sell

    If alt token is token0, a positive amount0 in the swap event indicates the alt token is leaving the pool (the user is buying it).
    If alt token is token1, check amount1 similarly.

These simple checks categorize each swap as “buy” or “sell” for your alt token.
3. Project Structure

A typical file layout:


    ├── config/
    │   ├── settings.py          # Contains constants (Alchemy URL, HEADERS, NUM_HOURS, BLOCKS_PER_HOUR, etc.)
    │   ├── coin_addresses.py    # Lists multiple tokens/pairs with pool addresses, alt token addresses, etc.
    ├── data_collection/
    │   ├── utils.py                 # Helper functions (RPC calls, decoding, calculations)
    │   ├── transaction_screener.py  # Main script orchestrating data flow
    └── README.md

3.1 config/settings.py

Defines environment-specific settings like:

    ALCHEMY_URL (string): Your Base (or other chain) RPC endpoint from Alchemy.
    HEADERS (dict): Typically {"Content-Type": "application/json"}.
    NUM_HOURS (int): How many approximate hours of logs to fetch for each run.
    BLOCKS_PER_HOUR (int): Approximates how many blocks pass in one hour on the chain.

3.2 config/coin_addresses.py

Holds a dictionary, e.g. COIN_ADDRESS_MAP_1, which enumerates each coin or trading pair. Example snippet:

    COIN_ADDRESS_MAP_1 = {
        "coins": {
            "ACT/WETH": {
                "pool_address": "0x269BDA0512de57Cd0BE0270686ffb3964C05e19b",
                "alt_token_address": "0xACT...",    # If known
            },
            "FROC/WETH": {
                "pool_address": "0x74F8A8c18010659A456C8584e625996AB62c1B62",
                "alt_token_address": "0xFROC...",
            },
            ...
        }
    }


3.3 utils.py

Implements RPC calls, decoding logic, and calculations, such as:

    get_latest_block()
    get_logs_in_range(...)
    get_token0(...), get_token1(...)
    detect_if_alt_token_is_token0(...)
    compute_price_in_quote_token(...)
    process_swap_log(...)

3.4 transaction_screener.py

The main script that:

    Reads COIN_ADDRESS_MAP_1.
    Iterates over each pair’s pool address.
    Auto-detects if the alt token is token0 or token1.
    Fetches logs for each hour chunk, decodes them, aggregates to a DataFrame.
    Outputs CSV files named after each pair.

4. Dependencies

Required Python Packages:

    requests: For making JSON-RPC calls to Alchemy.
    pandas: For data aggregation (group-bys, CSV output).
    eth-abi: For decoding the Swap event’s hexadecimal data field.
    time, math, etc. (standard libraries).

5. Configuration Files
5.1 settings.py

Example content:

    ALCHEMY_URL = "https://base-mainnet.g.alchemy.com/v2/<YOUR_API_KEY>"
    HEADERS = {"Content-Type": "application/json"}
    SWAP_TOPIC = "0xc42079f94a6350..."  # Keccak-256 of the UniV3 Swap(...) signature
    NUM_HOURS = 5
    BLOCKS_PER_HOUR = 1800

SWAP_TOPIC differs between UniV2 and UniV3. For UniV3, it’s commonly 0xc42079f9....

5.2 coin_addresses.py

Contains the dictionary that enumerates each coin pair under the "coins" key. Each entry typically has:

    pool_address: The actual Uniswap V3 pool contract.
    alt_token_address: The alt token’s contract address to detect whether it’s token0 or token1.

6. Data Flow and Workflow

Below is a high-level sequence describing how data flows through the project:

    Load Configuration
        The script imports settings.py to get ALCHEMY_URL, NUM_HOURS, etc.
        It imports coin_addresses.py to obtain a list of pools or coin pairs.

    Identify or Confirm Token Roles (Optional)
        Looks at alt_token_address, detect_if_alt_token_is_token0(pool, alt_address) calls get_token0() / get_token1() to see which side is alt token.

    Chunked Log Fetching
        The script calls get_latest_block() to find the current chain tip.
        Loops backward in increments of BLOCKS_PER_HOUR for NUM_HOURS cycles (approx. 1 hour each).
        Calls get_logs_in_range(from_block, to_block, pool_address) to retrieve all logs from the pool.

    Swap Event Decoding
        For each log in the returned list:
            process_swap_log(log, alt_token_is_token0) checks if it’s a recognized Swap event (matching S.SWAP_TOPIC).
            If so, extracts amount0, amount1, sqrtPriceX96, etc.
            Computes the alt token’s price in the quote token (e.g., WETH) via compute_price_in_quote_token(...).
            Classifies the trade as a buy or sell for the alt token.

    Data Aggregation
        All parsed swaps are stored in a list, then converted to a Pandas DataFrame:
            Columns include ["tx_hash", "amount0", "amount1", "price", "trade_type", "hour_index"].
        Using Pandas, the script groups swaps by (hour_index, trade_type) to count buys vs. sells, compute average price, etc.

    Output
        The result is saved to a CSV named after the pair, e.g. "FROC-WETH_swap_data.csv".
        The script prints a summary (buy/sell counts, average price) in the console.

7. Key Modules
7.1 utils.py (Selected Functions)

    get_latest_block()
        Calls eth_blockNumber and returns an integer for the chain’s latest block.

    get_logs_in_range(from_block, to_block, address)
        Calls eth_getLogs, retrieving all logs from address between from_block and to_block.
        Used in an hourly chunk loop to avoid too-large queries.

    get_token0(pool_address) / get_token1(pool_address)
        Use eth_call to read the immutables from the Uniswap V3 pool: which token is token0, which is token1.
        Return the addresses in lowercase hex.

    detect_if_alt_token_is_token0(pool_address, alt_token_address)
        Compares alt_token_address to whichever is returned by get_token0 / get_token1, returning a boolean that indicates if the alt token is token0 or token1.

    compute_price_in_quote_token(sqrt_price_x96, alt_token_is_token0)
        Squares sqrt_price_x96 and divides by 2^192 to get (token1 / token0).
        If alt_token_is_token0 is True, returns it directly; otherwise inverts.

    process_swap_log(log, alt_token_is_token0)
        Checks if log["topics"][0] matches the Swap topic.
        Decodes event data (amount0, amount1, sqrtPriceX96, etc.).
        Determines “buy” vs. “sell.”
        Returns a dictionary with tx_hash, amount0, amount1, price, and trade_type.

7.2 transaction_screener.py

Contains the main() function that:

    Iterates over coin pairs from coin_addresses.py.
    Optionally detects token0 vs. token1.
    Fetches logs in hour chunks and parses swaps.
    Groups and prints aggregated stats (buy/sell counts, average price).
    Saves the final DataFrame to CSV.