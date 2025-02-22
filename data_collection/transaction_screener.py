import requests
import time
import math
import pandas as pd
from eth_abi import abi  
from config import settings as S
from config.coin_addresses import COIN_ADDRESS_MAP_1 as C1

# --------------------------------------------------
# 1. Helper function: get latest block
# --------------------------------------------------
def get_latest_block() -> int:
    """
    Fetches the latest block number via Alchemy's JSON-RPC API.

    This function calls the 'eth_blockNumber' method on the configured EVM-based
    network (e.g., Ethereum mainnet, Base, etc.) according to the URL specified 
    in S.ALCHEMY_URL. It returns the most recent block's number as an integer.

    API Endpoint:
        - POST to S.ALCHEMY_URL using the standard Ethereum JSON-RPC 2.0 format.
        - Method: 'eth_blockNumber'.

    Returns:
        int: The latest block number in decimal format.

    Raises:
        KeyError: If the response JSON is missing the 'result' field.
        ValueError: If the result cannot be converted from hex to an integer.
        Exception: If the request fails or returns an unexpected response structure.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_blockNumber",
        "params": []
    }
    resp = requests.post(S.ALCHEMY_URL, headers=S.HEADERS, json=payload)
    data = resp.json()
    latest_block_hex = data.get("result")
    return int(latest_block_hex, 16)

# --------------------------------------------------
# 2. Helper function: get logs in range
# --------------------------------------------------
def get_logs_in_range(from_block: int, to_block: int, address: str) -> list:
    """
    Retrieves raw transaction logs from a specified block range via Alchemy's 'eth_getLogs'.

    This function queries an EVM-compatible node (e.g., Base or Ethereum) for all
    event logs emitted by a particular contract address between from_block and 
    to_block (inclusive). The returned logs can be parsed afterward to detect 
    swap events or any other specific event signatures.

    API Endpoint:
        - POST to S.ALCHEMY_URL with the 'eth_getLogs' method.
        - 'from_block' and 'to_block' are converted to hexadecimal strings.
        - 'address' should be the smart contract from which logs are needed (e.g., a 
          Uniswap V2/V3 pool or another DEX pool).

    Parameters:
        from_block (int): The starting block number (inclusive).
        to_block (int):   The ending block number (inclusive).
        address (str):    The contract address to filter logs by.

    Returns:
        list: A list of raw log entries (dictionaries), each containing topics,
              data fields, transaction hashes, and other log metadata.

    Raises:
        Exception: If the HTTP request fails, or if the response lacks a valid 'result'.
    """
    from_block_hex = hex(from_block)
    to_block_hex   = hex(to_block)

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_getLogs",
        "params": [
            {
                "fromBlock": from_block_hex,
                "toBlock":   to_block_hex,
                "address":   address
            }
        ]
    }

    resp = requests.post(S.ALCHEMY_URL, headers=S.HEADERS, json=payload)
    if resp.status_code != 200:
        raise Exception(f"HTTP error {resp.status_code}: {resp.text}")

    data = resp.json()
    if "result" in data:
        return data["result"]
    else:
        raise Exception(f"Error in get_logs_in_range: {data}")

# --------------------------------------------------
# 3. Decode a single Swap log (manual decode)
# --------------------------------------------------
def process_swap_log(log: dict, token_is_token0: bool = True) -> dict | None:
    """
    Decodes and processes a single Swap event from an EVM transaction log.

    This function manually extracts relevant data from a log entry corresponding 
    to a Uniswap V3-style Swap event. It relies on the event's data field being 
    structured as:
        (int256 amount0, int256 amount1, uint160 sqrtPriceX96, uint128 liquidity, int24 tick)

    Event Details:
        - Uniswap V3 emits a `Swap` event whenever a trade occurs.
        - The event contains, among other fields, the amounts of token0 and token1
          that changed hands, plus a sqrtPriceX96 used to derive the price.

    Decoding Method:
        - The `data` field (in hex) is decoded using `eth_abi.decode()`.
        - The decoded values include token amounts, sqrtPriceX96, and liquidity.
        - Trade direction (buy/sell) is deduced based on whether the token 
          is recognized as token0 or token1 in the pool.

    Price Calculation:
        - `sqrtPriceX96` is a Q64.96 fixed-point representation of the square root 
          of the price.
        - The formula for price (token1 per token0) is:
              price = (sqrtPriceX96 ** 2) / (2 ** 192)

    Parameters:
        log (dict): A single EVM log dictionary containing event topics and data.
        token_is_token0 (bool): If True, the token of interest is token0 in the pair; 
                                this determines how we infer buy vs. sell.

    Returns:
        dict | None:
            A dictionary with:
                - "tx_hash"   (str): The transaction hash of the swap.
                - "amount0"   (int): The signed amount for token0.
                - "amount1"   (int): The signed amount for token1.
                - "price"     (float): The derived price (token1 per token0).
                - "trade_type"(str): Either "buy" or "sell".
            Returns None if the log does not match a recognized Swap event signature.

    Raises:
        ValueError: If the data cannot be decoded properly.
        KeyError:   If required fields (topics or data) are missing or malformed.
    """
    topics = log.get("topics", [])
    if not topics or topics[0].lower() != S.SWAP_TOPIC:
        return None  # not a Swap event

    # Decode Swap event data:
    # Swap(address sender, address recipient, int256 amount0, int256 amount1,
    #      uint160 sqrtPriceX96, uint128 liquidity, int24 tick)
    #
    # Our decode signature with eth_abi:
    #   (int256 amount0, int256 amount1, uint160 sqrtPriceX96, uint128 liquidity, int256 tick)
    decoded = abi.decode(
        ["int256", "int256", "uint160", "uint128", "int256"],
        bytes.fromhex(log["data"][2:])
    )
    amount0        = decoded[0]
    amount1        = decoded[1]
    sqrt_price_x96 = decoded[2]
    # liquidity    = decoded[3]  # not needed at the moment
    # tick_raw     = decoded[4]

    # Determine buy vs sell (if token is token0, a positive amount0 means a buy)
    if token_is_token0:
        trade_type = "buy" if amount0 > 0 else "sell"
    else:
        trade_type = "buy" if amount1 > 0 else "sell"

    # Calculate price (token1 per token0) from sqrtPriceX96
    price = (sqrt_price_x96 ** 2) / (2 ** 192)

    # Return a dict with the info
    return {
        "tx_hash": log.get("transactionHash"),
        "amount0": amount0,
        "amount1": amount1,
        "price": price,
        "trade_type": trade_type
    }

# --------------------------------------------------
# 4. Main logic
# --------------------------------------------------
def main() -> None:
    """
    Orchestrates data collection, decoding, and basic analysis of Swap events.

    Workflow:
        1. Retrieves the latest block number via `get_latest_block()`.
        2. Iterates over the past `S.NUM_HOURS` approximate hours, determined by
           `S.BLOCKS_PER_HOUR` blocks each.
        3. For each hour chunk, fetches logs from Alchemy for the specified pool
           (`S.POOL_ADDRESS`).
        4. Decodes each log via `process_swap_log()`, identifying buy/sell swaps.
        5. Aggregates the collected swaps in a Pandas DataFrame.
        6. Summarizes buy/sell counts and computes average prices by hour.
        7. Saves the final DataFrame to 'swap_data.csv'.

    Outputs:
        - Prints status updates including the latest block number and how many 
          logs/swaps are found each hour.
        - Prints simple buy/sell counts per hour index.
        - Prints average price per hour.
        - Writes a CSV file ('swap_data.csv') for additional analysis.

    Raises:
        Exception: If any API calls fail or an unexpected result is returned.
        ValueError: If decoded swap data contains malformed or invalid values.
    """
    latest_block = get_latest_block()
    print("Latest block number:", latest_block)

    end_block = latest_block
    all_swaps = []  # store dicts of swap data here

    for hour_index in range(S.NUM_HOURS):
        start_block = max(end_block - S.BLOCKS_PER_HOUR, 0)
        print(f"Fetching logs for block range {start_block} to {end_block} (approx hour {hour_index+1})")

        logs = get_logs_in_range(start_block, end_block, S.POOL_ADDRESS)
        print(f"  Fetched {len(logs)} logs.")

        # Parse each log for swap data
        hour_swaps = []
        for log in logs:
            parsed = process_swap_log(log, S.TOKEN_IS_TOKEN0)
            if parsed is not None:
                # Tag with hour index or block range
                parsed["hour_index"] = hour_index + 1
                hour_swaps.append(parsed)

        print(f"  Found {len(hour_swaps)} Swap events in this chunk.")

        all_swaps.extend(hour_swaps)

        # Move range backward
        end_block = start_block - 1
        if end_block < 0:
            break

        # brief sleep to avoid spamming
        time.sleep(0.5)

    print(f"Total Swap events collected: {len(all_swaps)}")

    # 5. Convert to DataFrame for analysis
    df = pd.DataFrame(all_swaps)
    if df.empty:
        print("No swap data found!")
        return

    # 6. Show buy/sell counts by hour
    grouped = df.groupby(["hour_index", "trade_type"]).size().unstack(fill_value=0)
    print("\nBuy/Sell counts by hour_index:")
    print(grouped)

    # 7. Average price by hour
    avg_price = df.groupby("hour_index")["price"].mean()
    print("\nAverage price by hour:")
    print(avg_price)

    # 8. Save to CSV
    df.to_csv("swap_data.csv", index=False)
    print("\nSaved swap_data.csv with all events.")

if __name__ == "__main__":
    main()
