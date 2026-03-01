import logging
from collections import defaultdict
import requests
from config import CHAIN_CONFIGS, COINGECKO_BASE_URL, COINGECKO_RATE_LIMIT_PER_MIN, COINGECKO_API_KEY
from utils import RateLimiter, retry_request

logger = logging.getLogger("portfolio.pricing")

cg_limiter = RateLimiter(max_calls=COINGECKO_RATE_LIMIT_PER_MIN, period=60.0)
CG_HEADERS = {"x-cg-pro-api-key": COINGECKO_API_KEY} if COINGECKO_API_KEY else {}

BATCH_SIZE = 100  # CoinGecko max contract addresses per request


def fetch_native_token_prices() -> dict[str, float]:
    """Fetch prices for all native tokens. Returns {coingecko_id: usd_price}."""
    ids = set()
    for cfg in CHAIN_CONFIGS.values():
        ids.add(cfg["native_token"]["coingecko_id"])
    ids.add("solana")  # Always include SOL
    ids.add("hyperliquid")  # Always include HYPE

    ids_str = ",".join(ids)
    url = f"{COINGECKO_BASE_URL}/simple/price"

    cg_limiter.wait()

    def _fetch():
        resp = requests.get(url, params={"ids": ids_str, "vs_currencies": "usd"}, headers=CG_HEADERS, timeout=30)
        resp.raise_for_status()
        return resp.json()

    try:
        data = retry_request(_fetch)
        return {k: v.get("usd", 0) for k, v in data.items()}
    except Exception as e:
        logger.error(f"Failed to fetch native token prices: {e}")
        return {}


def fetch_token_prices_by_platform(platform_id: str, contract_addresses: list[str]) -> dict[str, float]:
    """Fetch USD prices for ERC-20/SPL tokens by contract address.
    Returns {contract_address_lower: usd_price}.
    """
    prices = {}

    for i in range(0, len(contract_addresses), BATCH_SIZE):
        batch = contract_addresses[i:i + BATCH_SIZE]
        addresses_str = ",".join(batch)
        url = f"{COINGECKO_BASE_URL}/simple/token_price/{platform_id}"

        cg_limiter.wait()

        def _fetch():
            resp = requests.get(
                url,
                params={"contract_addresses": addresses_str, "vs_currencies": "usd"},
                headers=CG_HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()

        try:
            data = retry_request(_fetch)
            for addr, price_data in data.items():
                usd = price_data.get("usd")
                if usd is not None:
                    prices[addr.lower()] = usd
        except Exception as e:
            logger.warning(f"Failed price fetch for {platform_id} batch {i}: {e}")

    return prices


def get_all_prices(holdings: list[dict]) -> dict[tuple[str, str], float]:
    """Build price lookup: (chain, contract_address) -> USD price.

    For native tokens, key is (chain, "native").
    For ERC-20/SPL tokens, key is (chain, contract_address_lower).
    """
    price_map: dict[tuple[str, str], float] = {}

    # 1. Native token prices
    native_prices = fetch_native_token_prices()
    for chain_key, cfg in CHAIN_CONFIGS.items():
        cg_id = cfg["native_token"]["coingecko_id"]
        if cg_id in native_prices:
            price_map[(chain_key, "native")] = native_prices[cg_id]
    if "solana" in native_prices:
        price_map[("solana", "native")] = native_prices["solana"]
    if "hyperliquid" in native_prices:
        price_map[("hyperliquid", "native")] = native_prices["hyperliquid"]

    # Hyperliquid special handling
    hl_spot_symbol_to_cg = {
        "usdc": "usd-coin", "usdt": "tether", "hype": "hyperliquid",
        "btc": "bitcoin", "eth": "ethereum", "sol": "solana",
        "arb": "arbitrum", "avax": "avalanche-2", "bnb": "binancecoin",
        "link": "chainlink", "uni": "uniswap", "aave": "aave",
        "op": "optimism", "matic": "matic-network", "doge": "dogecoin",
        "wif": "dogwifcoin", "pepe": "pepe", "bonk": "bonk",
    }
    hl_spot_ids = set()
    for h in holdings:
        if h["chain"] == "hyperliquid":
            if h["contract_address"] == "hl-perp-account":
                price_map[("hyperliquid", "hl-perp-account")] = 1.0
            elif h["contract_address"].startswith("hl-spot-"):
                sym = h["contract_address"].replace("hl-spot-", "")
                cg_id = hl_spot_symbol_to_cg.get(sym)
                if cg_id:
                    hl_spot_ids.add((sym, cg_id))

    if hl_spot_ids:
        cg_ids_str = ",".join(cg_id for _, cg_id in hl_spot_ids)
        cg_limiter.wait()
        try:
            def _fetch_hl():
                resp = requests.get(
                    f"{COINGECKO_BASE_URL}/simple/price",
                    params={"ids": cg_ids_str, "vs_currencies": "usd"},
                    headers=CG_HEADERS, timeout=30,
                )
                resp.raise_for_status()
                return resp.json()
            hl_prices = retry_request(_fetch_hl)
            for sym, cg_id in hl_spot_ids:
                usd = hl_prices.get(cg_id, {}).get("usd")
                if usd is not None:
                    price_map[("hyperliquid", f"hl-spot-{sym}")] = usd
        except Exception as e:
            logger.warning(f"Failed Hyperliquid spot price fetch: {e}")

    # 2. Group ERC-20/SPL contract addresses by platform
    platform_addresses: dict[str, set[str]] = defaultdict(set)
    for h in holdings:
        if h["contract_address"] == "native":
            continue
        chain = h["chain"]
        addr = h["contract_address"].lower()
        if chain == "solana":
            platform_addresses["solana"].add(addr)
        elif chain in CHAIN_CONFIGS:
            platform_id = CHAIN_CONFIGS[chain]["coingecko_platform"]
            platform_addresses[platform_id].add(addr)

    # 3. Fetch prices per platform
    for platform_id, addresses in platform_addresses.items():
        logger.info(f"Fetching prices for {len(addresses)} tokens on {platform_id}...")
        addr_list = sorted(addresses)
        prices = fetch_token_prices_by_platform(platform_id, addr_list)

        # Map back to (chain, contract_address) keys
        chain_key = _platform_to_chain(platform_id)
        for addr, usd_price in prices.items():
            price_map[(chain_key, addr)] = usd_price

    priced = sum(1 for v in price_map.values() if v is not None)
    logger.info(f"Prices resolved: {priced} tokens")

    return price_map


def _platform_to_chain(platform_id: str) -> str:
    if platform_id == "solana":
        return "solana"
    for chain_key, cfg in CHAIN_CONFIGS.items():
        if cfg["coingecko_platform"] == platform_id:
            return chain_key
    return platform_id
