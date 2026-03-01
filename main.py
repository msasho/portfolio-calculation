import os
import re
import time
from config import EVM_WALLETS, SOLANA_WALLETS, ALCHEMY_API_KEY, DUST_THRESHOLD_USD
from chains.evm import fetch_all_evm_balances
from chains.solana import fetch_all_solana_balances
from chains.hyperliquid import fetch_all_hyperliquid_balances
from pricing import get_all_prices
from aggregator import merge_balances_with_prices, filter_dust, generate_detailed_csv, generate_summary_csv, generate_cross_chain_csv
from utils import setup_logging

logger = setup_logging()

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def validate_inputs():
    if not ALCHEMY_API_KEY:
        raise ValueError("ALCHEMY_API_KEY is not set in .env")

    evm_pattern = re.compile(r"^0x[0-9a-fA-F]{40}$")
    for w in EVM_WALLETS:
        if not evm_pattern.match(w):
            raise ValueError(f"Invalid EVM wallet address: {w}")

    b58_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
    for w in SOLANA_WALLETS:
        if not (32 <= len(w) <= 44 and all(c in b58_chars for c in w)):
            raise ValueError(f"Invalid Solana wallet address: {w}")

    if not EVM_WALLETS and not SOLANA_WALLETS:
        raise ValueError("No wallet addresses configured. Set EVM_WALLETS and/or SOLANA_WALLETS in .env")


def print_summary(holdings: list[dict]):
    total_usd = sum(h["usd_value"] for h in holdings if h["usd_value"] is not None)
    priced_count = sum(1 for h in holdings if h["usd_value"] is not None)
    unpriced_count = sum(1 for h in holdings if h["usd_value"] is None)

    print("\n" + "=" * 70)
    print(f"  Portfolio Summary")
    print("=" * 70)
    print(f"  Total USD Value:  ${total_usd:,.2f}")
    print(f"  Tokens (priced):  {priced_count}")
    print(f"  Tokens (N/A):     {unpriced_count}")

    # --- Per-wallet breakdown ---
    from collections import defaultdict
    wallet_data = defaultdict(list)
    for h in holdings:
        wallet_data[h["wallet_address"]].append(h)

    for wallet, wallet_holdings in wallet_data.items():
        wallet_total = sum(h["usd_value"] for h in wallet_holdings if h["usd_value"] is not None)
        wallet_priced = [h for h in wallet_holdings if h["usd_value"] is not None]
        wallet_priced.sort(key=lambda h: h["usd_value"], reverse=True)

        print()
        print("-" * 70)
        print(f"  Wallet: {wallet}")
        print(f"  Subtotal: ${wallet_total:,.2f}")
        print()
        for h in wallet_priced:
            print(f"    {h['token_symbol']:>10s} on {h['chain']:<12s} "
                  f"${h['usd_value']:>12,.2f}  ({h['balance']:.6f})")
        unpriced = [h for h in wallet_holdings if h["usd_value"] is None and h["balance"] > 0]
        if unpriced:
            print(f"    ... + {len(unpriced)} tokens with no price data")

    # --- Overall Top 10 ---
    print()
    print("-" * 70)
    print("  Overall Top 10:")
    ranked = sorted(
        [h for h in holdings if h["usd_value"] is not None],
        key=lambda h: h["usd_value"],
        reverse=True,
    )
    for i, h in enumerate(ranked[:10], 1):
        addr_short = h["wallet_address"][:6] + ".." + h["wallet_address"][-4:]
        print(f"    {i:2d}. {h['token_symbol']:>10s} on {h['chain']:<12s} "
              f"${h['usd_value']:>12,.2f}  ({h['balance']:.6f})  [{addr_short}]")
    print("=" * 70 + "\n")


def main():
    start = time.time()
    logger.info("Starting portfolio calculation...")

    validate_inputs()
    logger.info(f"EVM wallets: {len(EVM_WALLETS)}, Solana wallets: {len(SOLANA_WALLETS)}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Phase 1: Fetch balances
    all_holdings = []

    if EVM_WALLETS:
        logger.info("=== Fetching EVM balances ===")
        evm_holdings = fetch_all_evm_balances(EVM_WALLETS)
        all_holdings.extend(evm_holdings)
        logger.info(f"EVM total: {len(evm_holdings)} token entries")

    if SOLANA_WALLETS:
        logger.info("=== Fetching Solana balances ===")
        sol_holdings = fetch_all_solana_balances(SOLANA_WALLETS)
        all_holdings.extend(sol_holdings)
        logger.info(f"Solana total: {len(sol_holdings)} token entries")

    # Hyperliquid (uses EVM wallet addresses)
    if EVM_WALLETS:
        logger.info("=== Fetching Hyperliquid balances ===")
        hl_holdings = fetch_all_hyperliquid_balances(EVM_WALLETS)
        all_holdings.extend(hl_holdings)
        logger.info(f"Hyperliquid total: {len(hl_holdings)} token entries")

    if not all_holdings:
        logger.info("No tokens found across any wallet/chain.")
        return

    # Phase 2: Fetch prices
    logger.info("=== Fetching prices ===")
    prices = get_all_prices(all_holdings)
    all_holdings = merge_balances_with_prices(all_holdings, prices)

    # Phase 3: Filter and output
    all_holdings = filter_dust(all_holdings, DUST_THRESHOLD_USD)
    logger.info(f"After dust filter (>${DUST_THRESHOLD_USD}): {len(all_holdings)} tokens")

    generate_detailed_csv(all_holdings, OUTPUT_DIR)
    generate_summary_csv(all_holdings, OUTPUT_DIR)
    generate_cross_chain_csv(all_holdings, OUTPUT_DIR)

    print_summary(all_holdings)

    elapsed = time.time() - start
    logger.info(f"Done in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
