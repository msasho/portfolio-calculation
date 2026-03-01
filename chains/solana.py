import logging
import requests
from config import HELIUS_API_KEY
from utils import json_rpc_request, RateLimiter, retry_request

logger = logging.getLogger("portfolio.solana")

solana_limiter = RateLimiter(max_calls=8, period=1.0)

_jupiter_token_map: dict[str, dict] | None = None

SPL_TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
SPL_TOKEN_2022_PROGRAM = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"


def _get_rpc_url() -> str:
    if HELIUS_API_KEY:
        return f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
    return "https://api.mainnet-beta.solana.com"


def load_jupiter_token_map() -> dict[str, dict]:
    global _jupiter_token_map
    if _jupiter_token_map is not None:
        return _jupiter_token_map

    logger.info("Loading Jupiter token list...")

    def _fetch():
        resp = requests.get("https://token.jup.ag/all", timeout=30)
        resp.raise_for_status()
        return resp.json()

    try:
        tokens = retry_request(_fetch)
        _jupiter_token_map = {}
        for t in tokens:
            _jupiter_token_map[t["address"]] = {
                "symbol": t.get("symbol", ""),
                "name": t.get("name", ""),
                "decimals": t.get("decimals", 0),
            }
        logger.info(f"Loaded {len(_jupiter_token_map)} tokens from Jupiter")
    except Exception as e:
        logger.warning(f"Failed to load Jupiter token list: {e}")
        _jupiter_token_map = {}

    return _jupiter_token_map


def fetch_native_sol_balance(wallet: str, rpc_url: str) -> dict:
    result = json_rpc_request(rpc_url, "getBalance", [wallet], solana_limiter)
    lamports = result.get("value", 0)
    balance = lamports / 1e9
    return {
        "token_symbol": "SOL",
        "token_name": "Solana",
        "chain": "solana",
        "wallet_address": wallet,
        "contract_address": "native",
        "balance": balance,
        "decimals": 9,
    }


def fetch_spl_balances(wallet: str, rpc_url: str, program_id: str, token_map: dict) -> list[dict]:
    result = json_rpc_request(
        rpc_url,
        "getTokenAccountsByOwner",
        [wallet, {"programId": program_id}, {"encoding": "jsonParsed"}],
        solana_limiter,
    )

    holdings = []
    for account in result.get("value", []):
        info = account.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
        mint = info.get("mint", "")
        token_amount = info.get("tokenAmount", {})
        ui_amount = token_amount.get("uiAmount")
        decimals = token_amount.get("decimals", 0)

        if not ui_amount or ui_amount == 0:
            continue

        meta = token_map.get(mint, {})
        holdings.append({
            "token_symbol": meta.get("symbol") or mint[:8],
            "token_name": meta.get("name") or "Unknown",
            "chain": "solana",
            "wallet_address": wallet,
            "contract_address": mint,
            "balance": ui_amount,
            "decimals": decimals,
        })

    return holdings


def fetch_all_solana_balances(wallets: list[str]) -> list[dict]:
    if not wallets:
        return []

    rpc_url = _get_rpc_url()
    token_map = load_jupiter_token_map()
    all_holdings = []

    for wallet in wallets:
        logger.info(f"Fetching Solana balances for {wallet[:10]}...")

        # Native SOL
        try:
            sol = fetch_native_sol_balance(wallet, rpc_url)
            if sol["balance"] > 0:
                all_holdings.append(sol)
        except Exception as e:
            logger.error(f"Failed SOL balance for {wallet[:10]}: {e}")

        # SPL tokens (standard + Token-2022)
        for program_id in [SPL_TOKEN_PROGRAM, SPL_TOKEN_2022_PROGRAM]:
            try:
                tokens = fetch_spl_balances(wallet, rpc_url, program_id, token_map)
                all_holdings.extend(tokens)
            except Exception as e:
                logger.error(f"Failed SPL balances for {wallet[:10]}: {e}")

        logger.info(f"  Found {len(all_holdings)} tokens on Solana")

    return all_holdings
