import logging
from config import CHAIN_CONFIGS, ALCHEMY_API_KEY
from utils import json_rpc_request, RateLimiter

logger = logging.getLogger("portfolio.evm")

_metadata_cache: dict[tuple[str, str], dict] = {}

alchemy_limiter = RateLimiter(max_calls=5, period=1.0)


def _alchemy_url(chain_key: str) -> str:
    slug = CHAIN_CONFIGS[chain_key]["alchemy_slug"]
    return f"https://{slug}.g.alchemy.com/v2/{ALCHEMY_API_KEY}"


def _is_zero_balance(hex_balance: str) -> bool:
    if not hex_balance or hex_balance in ("0x", "0x0"):
        return True
    try:
        return int(hex_balance, 16) == 0
    except ValueError:
        return True


def fetch_native_balance(chain_key: str, wallet: str) -> dict:
    url = _alchemy_url(chain_key)
    result = json_rpc_request(url, "eth_getBalance", [wallet, "latest"], alchemy_limiter)
    native = CHAIN_CONFIGS[chain_key]["native_token"]
    raw = int(result, 16)
    balance = raw / (10 ** native["decimals"])
    return {
        "token_symbol": native["symbol"],
        "token_name": CHAIN_CONFIGS[chain_key]["name"],
        "chain": chain_key,
        "wallet_address": wallet,
        "contract_address": "native",
        "balance": balance,
        "decimals": native["decimals"],
    }


def fetch_erc20_balances(chain_key: str, wallet: str) -> list[dict]:
    url = _alchemy_url(chain_key)
    all_tokens = []
    page_key = None

    while True:
        params = [wallet, "erc20"]
        if page_key:
            params = [wallet, "erc20", {"pageKey": page_key}]

        result = json_rpc_request(url, "alchemy_getTokenBalances", params, alchemy_limiter)

        for tb in result.get("tokenBalances", []):
            if not _is_zero_balance(tb.get("tokenBalance")):
                all_tokens.append({
                    "contract_address": tb["contractAddress"],
                    "balance_raw": tb["tokenBalance"],
                })

        page_key = result.get("pageKey")
        if not page_key:
            break

    return all_tokens


def fetch_token_metadata(chain_key: str, contract_address: str) -> dict:
    cache_key = (chain_key, contract_address.lower())
    if cache_key in _metadata_cache:
        return _metadata_cache[cache_key]

    url = _alchemy_url(chain_key)
    try:
        result = json_rpc_request(url, "alchemy_getTokenMetadata", [contract_address], alchemy_limiter)
        meta = {
            "symbol": result.get("symbol") or contract_address[:10],
            "name": result.get("name") or "Unknown",
            "decimals": result.get("decimals") or 18,
        }
    except Exception as e:
        logger.warning(f"Failed to get metadata for {contract_address} on {chain_key}: {e}")
        meta = {"symbol": contract_address[:10], "name": "Unknown", "decimals": 18}

    _metadata_cache[cache_key] = meta
    return meta


def get_wallet_balances(chain_key: str, wallet: str) -> list[dict]:
    holdings = []

    # Native balance
    try:
        native = fetch_native_balance(chain_key, wallet)
        if native["balance"] > 0:
            holdings.append(native)
    except Exception as e:
        logger.error(f"Failed native balance for {wallet} on {chain_key}: {e}")

    # ERC-20 balances
    try:
        tokens = fetch_erc20_balances(chain_key, wallet)
    except Exception as e:
        logger.error(f"Failed ERC-20 balances for {wallet} on {chain_key}: {e}")
        return holdings

    for token in tokens:
        meta = fetch_token_metadata(chain_key, token["contract_address"])
        raw = int(token["balance_raw"], 16)
        decimals = meta["decimals"]
        balance = raw / (10 ** decimals) if decimals else float(raw)

        holdings.append({
            "token_symbol": meta["symbol"],
            "token_name": meta["name"],
            "chain": chain_key,
            "wallet_address": wallet,
            "contract_address": token["contract_address"].lower(),
            "balance": balance,
            "decimals": decimals,
        })

    return holdings


def fetch_all_evm_balances(wallets: list[str]) -> list[dict]:
    all_holdings = []

    for chain_key in CHAIN_CONFIGS:
        for wallet in wallets:
            logger.info(f"Fetching {CHAIN_CONFIGS[chain_key]['name']} balances for {wallet[:10]}...")
            try:
                holdings = get_wallet_balances(chain_key, wallet)
                all_holdings.extend(holdings)
                logger.info(f"  Found {len(holdings)} tokens")
            except Exception as e:
                logger.error(f"Failed {chain_key} for {wallet[:10]}: {e}")

    return all_holdings
