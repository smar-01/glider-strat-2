import requests
from eth_abi import abi
from config import settings as S

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

def get_token0(pool_address: str) -> str:
    """
    Retrieves the address of 'token0' from a Uniswap V3 pool contract via Alchemy’s JSON-RPC.

    This function issues an 'eth_call' to invoke the 'token0()' view method on the
    specified Uniswap V3 pool contract. The contract returns a 32-byte value, where
    the last 20 bytes represent the token0 address. This address is then converted
    to lowercase hex and returned as a string.

    API Endpoint:
        - POST to S.ALCHEMY_URL using the standard Ethereum JSON-RPC 2.0 format.
        - Method: 'eth_call' with the function selector 0x0dfe1681 (keccak256("token0()")[:4]).

    Parameters:
        pool_address (str): The Uniswap V3 pool contract address.

    Returns:
        str: The 20-byte 'token0' address in lowercase 0x-prefixed hex.

    Raises:
        Exception: If the request fails or the JSON response is malformed.
    """
    # 0x0dfe1681 is the 4-byte function selector for token0()
    data = "0x0dfe1681"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [
            {
                "to": pool_address,
                "data": data
            },
            "latest"
        ]
    }
    resp = requests.post(S.ALCHEMY_URL, headers=S.HEADERS, json=payload)
    result_hex = resp.json().get("result")
    # last 20 bytes is the token0 address
    return "0x" + result_hex[-40:].lower()

def get_token1(pool_address: str) -> str:
    """
    Retrieves the address of 'token1' from a Uniswap V3 pool contract via Alchemy’s JSON-RPC.

    Similar to 'get_token0()', this function calls the 'token1()' view method
    on a Uniswap V3 pool contract using an 'eth_call'. The contract returns a 32-byte value,
    from which the last 20 bytes correspond to the token1 address. This is lowercased and
    returned as a 0x-prefixed string.

    API Endpoint:
        - POST to S.ALCHEMY_URL using the standard Ethereum JSON-RPC 2.0 format.
        - Method: 'eth_call' with the function selector 0xd21220a7 (keccak256("token1()")[:4]).

    Parameters:
        pool_address (str): The Uniswap V3 pool contract address.

    Returns:
        str: The 20-byte 'token1' address in lowercase 0x-prefixed hex.

    Raises:
        Exception: If the request fails or the JSON response is malformed.
    """
    # 0xd21220a7 is the 4-byte function selector for token1()
    data = "0xd21220a7"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [
            {
                "to": pool_address,
                "data": data
            },
            "latest"
        ]
    }
    resp = requests.post(S.ALCHEMY_URL, headers=S.HEADERS, json=payload)
    result_hex = resp.json().get("result")
    return "0x" + result_hex[-40:].lower()

def detect_if_alt_token_is_token0(pool_address: str, alt_token_address: str) -> bool:
    """
    Determines whether a given alt token address is 'token0' or 'token1' in a Uniswap V3 pool.

    Internally, this function calls 'get_token0()' and 'get_token1()' on the pool and compares
    those addresses with 'alt_token_address'. If 'alt_token_address' matches 'token0', it returns True;
    if it matches 'token1', it returns False. Otherwise, it raises an exception indicating a mismatch.

    Parameters:
        pool_address (str): The Uniswap V3 pool contract address.
        alt_token_address (str): The alt token address to check (e.g., BNKR or ACT).

    Returns:
        bool:
            - True if 'alt_token_address' is token0 in the pool.
            - False if 'alt_token_address' is token1 in the pool.

    Raises:
        Exception: If the alt token address does not match either 'token0' or 'token1'.
    """
    t0 = get_token0(pool_address)
    t1 = get_token1(pool_address)

    if alt_token_address.lower() == t0.lower():
        return True
    elif alt_token_address.lower() == t1.lower():
        return False
    else:
        raise Exception(
            f"Pool {pool_address} does not have {alt_token_address} as token0 or token1.\n"
            f"Found token0={t0}, token1={t1} instead."
        )
    
def compute_price_in_quote_token(sqrt_price_x96: int, alt_token_is_token0: bool) -> float:
    """
    Computes the price of an alt token in terms of a quote token (e.g. WETH, USDC) using Uniswap V3’s sqrtPriceX96.

    Uniswap V3 represents its price as the square root of (token1 / token0), scaled by 2^96.
    If the alt token is token0, then (sqrtPriceX96^2 / 2^192) yields “quoteToken per altToken.”
    If the alt token is token1, we invert that value to get “quoteToken per altToken.”
    
    Parameters:
        sqrt_price_x96 (int): The 160-bit sqrt(price) value from a Swap event log.
        alt_token_is_token0 (bool): True if the alt token is token0 in the pool; otherwise False.

    Returns:
        float: The price of the alt token in the quote token (e.g., WETH).

    Example:
        If sqrt_price_x96^2/2^192 ≈ 0.000001 WETH per alt token when alt_token_is_token0 = True,
        the function returns 0.000001. If alt_token_is_token0 = False, the function inverts that number.

    Raises:
        ValueError: If sqrt_price_x96 is invalid or outside typical Uniswap V3 ranges.
    """
    # raw_price = token1/token0
    raw_price = (sqrt_price_x96 ** 2) / (2 ** 192)

    if alt_token_is_token0:
        # raw_price is WETH per alt token => that's good if token1 = WETH
        return raw_price
    else:
        # raw_price is alt_token per WETH => invert to get WETH per alt token
        return 1 / raw_price

def process_swap_log(log: dict, alt_token_is_token0: bool) -> dict | None:
    """
    Decodes and processes a single Swap event from a Uniswap V3 pool log.

    The function checks whether the given log matches the configured Swap event
    signature (S.SWAP_TOPIC). If it does, it decodes the data section, which is 
    expected to contain:

        (int256 amount0, int256 amount1, uint160 sqrtPriceX96, uint128 liquidity, int24 tick)

    Uniswap V3 records amounts of token0 and token1 swapped, plus a sqrtPriceX96 value 
    that reflects the final pool price after the swap.

    Buy/Sell Logic:
        - If the alt token is token0, a positive amount0 indicates a "buy" of that token 
          (the pool is sending out alt tokens).
        - If the alt token is token1, a positive amount1 indicates a "buy."

    Price Calculation:
        - The function calls 'compute_price_in_quote_token' to derive the alt token's price 
          in quote token units (e.g., WETH). This leverages sqrtPriceX96, which is the 
          square root of (token1/token0) scaled by 2^96. The final value represents 
          quoteToken per altToken if alt_token_is_token0 is True, or its inverse otherwise.

    Parameters:
        log (dict): A dictionary representing a single swap log, including 'topics' and 'data'.
        alt_token_is_token0 (bool): Indicates whether the alt token is token0 in the pool 
                                    (affects trade_type and price calculation).

    Returns:
        dict | None:
            - A dictionary with:
                "tx_hash"    (str):  Transaction hash of the swap.
                "amount0"    (int):  Signed amount of token0 swapped.
                "amount1"    (int):  Signed amount of token1 swapped.
                "price"      (float): Alt token price in the quote token (e.g., WETH).
                "trade_type" (str):  "buy" or "sell".
            - None if this log does not match the Swap event signature.

    Raises:
        ValueError: If the log’s data cannot be decoded properly or contains invalid values.
        KeyError:   If the expected 'topics' or 'data' fields are missing in the log.
    """
    topics = log.get("topics", [])
    if not topics or topics[0].lower() != S.SWAP_TOPIC.lower():
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
    if alt_token_is_token0:
        trade_type = "buy" if amount0 > 0 else "sell"
    else:
        trade_type = "buy" if amount1 > 0 else "sell"

    # Calculate price (token1 per token0) from sqrtPriceX96
    price_in_quote = compute_price_in_quote_token(sqrt_price_x96, alt_token_is_token0)

    # Return a dict with the info
    return {
        "tx_hash": log.get("transactionHash"),
        "amount0": amount0,
        "amount1": amount1,
        "price": price_in_quote,
        "trade_type": trade_type
    }






