
from settings_private import ALCHEMY_API_KEY

ALCHEMY_URL = f"https://base-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
HEADERS = {"Content-Type": "application/json"}
BLOCKS_PER_HOUR = 1800    # approximate for Base (adjust if needed)
NUM_HOURS       = 5       # how many hourly chunks to want?

# If token is token0 in the pool, set this to True
# TOKEN_IS_TOKEN0 = False

# Uniswap V3 "Swap" event signature (Keccak-256 of Swap(...) )
SWAP_TOPIC = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"
