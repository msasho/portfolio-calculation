import os
from dotenv import load_dotenv

load_dotenv()

ALCHEMY_API_KEY = os.getenv("ALCHEMY_API_KEY", "")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY", "")
DUST_THRESHOLD_USD = float(os.getenv("DUST_THRESHOLD_USD", "1.0"))

EVM_WALLETS = [w.strip() for w in os.getenv("EVM_WALLETS", "").split(",") if w.strip()]
SOLANA_WALLETS = [w.strip() for w in os.getenv("SOLANA_WALLETS", "").split(",") if w.strip()]

COINGECKO_API_KEY = os.getenv("COIN_GECKO_API_KEY", "")
COINGECKO_BASE_URL = (
    "https://pro-api.coingecko.com/api/v3" if COINGECKO_API_KEY
    else "https://api.coingecko.com/api/v3"
)
COINGECKO_RATE_LIMIT_PER_MIN = 500 if COINGECKO_API_KEY else 30

CHAIN_CONFIGS = {
    "ethereum": {
        "name": "Ethereum",
        "alchemy_slug": "eth-mainnet",
        "chain_id": 1,
        "coingecko_platform": "ethereum",
        "native_token": {"symbol": "ETH", "coingecko_id": "ethereum", "decimals": 18},
    },
    "arbitrum": {
        "name": "Arbitrum",
        "alchemy_slug": "arb-mainnet",
        "chain_id": 42161,
        "coingecko_platform": "arbitrum-one",
        "native_token": {"symbol": "ETH", "coingecko_id": "ethereum", "decimals": 18},
    },
    "optimism": {
        "name": "Optimism",
        "alchemy_slug": "opt-mainnet",
        "chain_id": 10,
        "coingecko_platform": "optimistic-ethereum",
        "native_token": {"symbol": "ETH", "coingecko_id": "ethereum", "decimals": 18},
    },
    "base": {
        "name": "Base",
        "alchemy_slug": "base-mainnet",
        "chain_id": 8453,
        "coingecko_platform": "base",
        "native_token": {"symbol": "ETH", "coingecko_id": "ethereum", "decimals": 18},
    },
    "polygon": {
        "name": "Polygon",
        "alchemy_slug": "polygon-mainnet",
        "chain_id": 137,
        "coingecko_platform": "polygon-pos",
        "native_token": {"symbol": "POL", "coingecko_id": "matic-network", "decimals": 18},
    },
    "bsc": {
        "name": "BNB Smart Chain",
        "alchemy_slug": "bnb-mainnet",
        "chain_id": 56,
        "coingecko_platform": "binance-smart-chain",
        "native_token": {"symbol": "BNB", "coingecko_id": "binancecoin", "decimals": 18},
    },
    "avalanche": {
        "name": "Avalanche",
        "alchemy_slug": "avax-mainnet",
        "chain_id": 43114,
        "coingecko_platform": "avalanche",
        "native_token": {"symbol": "AVAX", "coingecko_id": "avalanche-2", "decimals": 18},
    },
}
