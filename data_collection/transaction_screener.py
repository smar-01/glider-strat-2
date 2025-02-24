import requests
import time
import math
import pandas as pd
from eth_abi import abi  
from config import settings as S
from config.coin_addresses import COIN_ADDRESS_MAP_1 as C1
from .utils import (
    get_latest_block,
    get_logs_in_range,
    process_swap_log,
    detect_if_alt_token_is_token0
)

def main() -> None:
    """
    Orchestrates the retrieval, decoding, and basic analysis of Swap events for multiple pools.

    For each token pair listed in C1["coins"], this workflow:
      1. Determines whether the alt token is token0 or token1 in the Uniswap V3 pool 
         (detect_if_alt_token_is_token0).
      2. Fetches logs in hourly chunks (defined by S.NUM_HOURS and S.BLOCKS_PER_HOUR).
      3. Decodes the logs via process_swap_log, categorizing swaps as "buy" or "sell."
      4. Aggregates the results into a Pandas DataFrame, computing buy/sell counts and
         average price per hour.
      5. Exports the results to a CSV file named after the token pair.

    Console Output:
      - Latest block number.
      - Per-hour log fetch status (start_block, end_block).
      - Total Swap events found in each chunk and overall.
      - Buy/Sell breakdown per hour_index.
      - Average price by hour_index.
      - Name of the output CSV file.

    Raises:
      Exception: If any Alchemy API call fails or returns unexpected data.
      ValueError: If decoded swap data is malformed (e.g., missing fields).
    """
    latest_block = get_latest_block()
    print("Latest block number:", latest_block)

    for pair_name, coin_info in C1["coins"].items():
        pool_address = coin_info["pool_address"]

        # If config has alt_token_address, you can do:
        alt_token_address = coin_info["alt_token_address"]
        # figure out whether alt token in token0
        token_is_token0 = detect_if_alt_token_is_token0(pool_address, alt_token_address)

        end_block = latest_block
        all_swaps = []  # store dicts of swap data here

        for hour_index in range(S.NUM_HOURS):
            start_block = max(end_block - S.BLOCKS_PER_HOUR, 0)
            print(f"[{pair_name}] Hour {hour_index+1}: blocks {start_block} to {end_block}")

            logs = get_logs_in_range(start_block, end_block, pool_address)
            print(f"  Fetched {len(logs)} logs for {pair_name}")

            # Parse each log for swap data
            hour_swaps = []
            for log in logs:
                parsed = process_swap_log(log, token_is_token0)
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
            print(f"No swap data for {pair_name}!")
            continue

        # 6. Show buy/sell counts by hour
        grouped = df.groupby(["hour_index", "trade_type"]).size().unstack(fill_value=0)
        print("\nBuy/Sell counts by hour_index:")
        print(grouped)

        # 7. Average price by hour
        avg_price = df.groupby("hour_index")["price"].mean()
        print("\nAverage price by hour:")
        print(avg_price)

        # 8. Save to CSV
        csv_filename = pair_name.replace("/", "-") + "_swap_data.csv"
        df.to_csv(csv_filename, index=False)
        print(f"Saved {csv_filename} with {len(df)} swap events.\n")

        #return # only do first in loop for now

if __name__ == "__main__":
    main()
