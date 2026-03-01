import logging
import requests
from utils import retry_request, json_rpc_request, RateLimiter

logger = logging.getLogger("portfolio.hyperliquid")

HYPERLIQUID_INFO_URL = "https://api.hyperliquid.xyz/info"
HYPEREVM_RPC_URL = "https://rpc.hyperliquid.xyz"

hl_limiter = RateLimiter(max_calls=5, period=1.0)


def _info_request(payload: dict) -> dict:
    hl_limiter.wait()

    def _fetch():
        resp = requests.post(HYPERLIQUID_INFO_URL, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    return retry_request(_fetch)


def fetch_hyperevm_native_balance(wallet: str) -> dict | None:
    """Fetch native HYPE balance on HyperEVM via eth_getBalance."""
    try:
        result = json_rpc_request(HYPEREVM_RPC_URL, "eth_getBalance", [wallet, "latest"], hl_limiter)
        raw = int(result, 16)
        balance = raw / 1e18
        if balance > 0:
            return {
                "token_symbol": "HYPE",
                "token_name": "Hyperliquid",
                "chain": "hyperliquid",
                "wallet_address": wallet,
                "contract_address": "native",
                "balance": balance,
                "decimals": 18,
            }
    except Exception as e:
        logger.error(f"Failed HyperEVM native balance for {wallet[:10]}: {e}")
    return None


def fetch_spot_balances(wallet: str) -> list[dict]:
    """Fetch Hyperliquid spot (L1) balances."""
    holdings = []
    try:
        data = _info_request({"type": "spotClearinghouseState", "user": wallet})
        for bal in data.get("balances", []):
            token = bal.get("coin", "")
            total = float(bal.get("total", 0))
            if total > 0:
                holdings.append({
                    "token_symbol": token,
                    "token_name": token,
                    "chain": "hyperliquid",
                    "wallet_address": wallet,
                    "contract_address": f"hl-spot-{token.lower()}",
                    "balance": total,
                    "decimals": 0,
                })
    except Exception as e:
        logger.error(f"Failed Hyperliquid spot balances for {wallet[:10]}: {e}")
    return holdings


def fetch_perp_account_value(wallet: str) -> list[dict]:
    """Fetch Hyperliquid perp account value (margin + unrealized PnL)."""
    holdings = []
    try:
        data = _info_request({"type": "clearinghouseState", "user": wallet})
        margin_summary = data.get("marginSummary", {})
        account_value = float(margin_summary.get("accountValue", 0))
        if account_value > 0:
            holdings.append({
                "token_symbol": "USDC(perp)",
                "token_name": "Hyperliquid Perp Account",
                "chain": "hyperliquid",
                "wallet_address": wallet,
                "contract_address": "hl-perp-account",
                "balance": account_value,
                "decimals": 0,
            })
    except Exception as e:
        logger.error(f"Failed Hyperliquid perp state for {wallet[:10]}: {e}")
    return holdings


def fetch_all_hyperliquid_balances(wallets: list[str]) -> list[dict]:
    all_holdings = []

    for wallet in wallets:
        logger.info(f"Fetching Hyperliquid balances for {wallet[:10]}...")

        # HyperEVM native HYPE
        native = fetch_hyperevm_native_balance(wallet)
        if native:
            all_holdings.append(native)

        # Spot balances (L1)
        spot = fetch_spot_balances(wallet)
        all_holdings.extend(spot)

        # Perp account value
        perp = fetch_perp_account_value(wallet)
        all_holdings.extend(perp)

        logger.info(f"  Found {len(spot) + len(perp) + (1 if native else 0)} entries on Hyperliquid")

    return all_holdings
