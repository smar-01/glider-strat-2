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
def get_latest_block():
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
def get_logs_in_range(from_block, to_block, address):
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
def process_swap_log(log, token_is_token0=True):
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
    # liquidity    = decoded[3]  # notn eeded atm
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
def main():
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

    # 6. Example: show buy/sell counts by hour
    grouped = df.groupby(["hour_index", "trade_type"]).size().unstack(fill_value=0)
    print("\nBuy/Sell counts by hour_index:")
    print(grouped)

    # 7. Example: average price by hour
    avg_price = df.groupby("hour_index")["price"].mean()
    print("\nAverage price by hour:")
    print(avg_price)

    # 8. Save to CSV
    df.to_csv("swap_data.csv", index=False)
    print("\nSaved swap_data.csv with all events.")

if __name__ == "__main__":
    main()
