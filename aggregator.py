import csv
import os
import logging
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger("portfolio.aggregator")


def merge_balances_with_prices(holdings: list[dict], prices: dict[tuple[str, str], float]) -> list[dict]:
    for h in holdings:
        key = (h["chain"], h["contract_address"].lower() if h["contract_address"] != "native" else "native")
        usd_price = prices.get(key)
        h["usd_price"] = usd_price
        h["usd_value"] = h["balance"] * usd_price if usd_price is not None else None
    return holdings


def filter_dust(holdings: list[dict], threshold_usd: float) -> list[dict]:
    return [
        h for h in holdings
        if h["usd_value"] is None or h["usd_value"] >= threshold_usd
    ]


def generate_detailed_csv(holdings: list[dict], output_dir: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"portfolio_detail_{ts}.csv")

    sorted_holdings = sorted(holdings, key=lambda h: (h["usd_value"] or 0), reverse=True)

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "token_symbol", "token_name", "chain", "wallet_address",
            "contract_address", "balance", "usd_price", "usd_value",
        ])
        for h in sorted_holdings:
            writer.writerow([
                h["token_symbol"],
                h["token_name"],
                h["chain"],
                h["wallet_address"],
                h["contract_address"],
                f"{h['balance']:.8f}",
                f"{h['usd_price']:.4f}" if h["usd_price"] is not None else "N/A",
                f"{h['usd_value']:.2f}" if h["usd_value"] is not None else "N/A",
            ])

    logger.info(f"Detailed CSV: {filepath}")
    return filepath


def generate_summary_csv(holdings: list[dict], output_dir: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"portfolio_summary_{ts}.csv")

    # Aggregate by (token_symbol, chain)
    agg: dict[tuple[str, str], dict] = defaultdict(lambda: {
        "token_name": "", "total_balance": 0.0, "usd_price": None, "total_usd_value": 0.0,
    })

    for h in holdings:
        key = (h["token_symbol"], h["chain"])
        entry = agg[key]
        entry["token_name"] = h["token_name"]
        entry["total_balance"] += h["balance"]
        if h["usd_price"] is not None:
            entry["usd_price"] = h["usd_price"]
        if h["usd_value"] is not None:
            entry["total_usd_value"] += h["usd_value"]

    rows = []
    for (symbol, chain), data in agg.items():
        rows.append({
            "token_symbol": symbol,
            "token_name": data["token_name"],
            "chain": chain,
            "total_balance": data["total_balance"],
            "usd_price": data["usd_price"],
            "total_usd_value": data["total_usd_value"] if data["usd_price"] is not None else None,
        })

    rows.sort(key=lambda r: (r["total_usd_value"] or 0), reverse=True)

    grand_total = sum(r["total_usd_value"] for r in rows if r["total_usd_value"] is not None)

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "token_symbol", "token_name", "chain",
            "total_balance", "usd_price", "total_usd_value",
        ])
        for r in rows:
            writer.writerow([
                r["token_symbol"],
                r["token_name"],
                r["chain"],
                f"{r['total_balance']:.8f}",
                f"{r['usd_price']:.4f}" if r["usd_price"] is not None else "N/A",
                f"{r['total_usd_value']:.2f}" if r["total_usd_value"] is not None else "N/A",
            ])
        writer.writerow(["TOTAL", "", "", "", "", f"{grand_total:.2f}"])

    logger.info(f"Summary CSV: {filepath}")
    return filepath


def generate_cross_chain_csv(holdings: list[dict], output_dir: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"portfolio_cross_chain_{ts}.csv")

    # Aggregate by token_symbol across all chains
    agg: dict[str, dict] = defaultdict(lambda: {
        "total_balance": 0.0, "total_usd_value": 0.0, "chains": set(), "has_price": False,
    })

    for h in holdings:
        entry = agg[h["token_symbol"]]
        entry["total_balance"] += h["balance"]
        entry["chains"].add(h["chain"])
        if h["usd_value"] is not None:
            entry["total_usd_value"] += h["usd_value"]
            entry["has_price"] = True

    rows = []
    for symbol, data in agg.items():
        rows.append({
            "token_symbol": symbol,
            "total_balance": data["total_balance"],
            "total_usd_value": data["total_usd_value"] if data["has_price"] else None,
            "chains": ", ".join(sorted(data["chains"])),
        })

    rows.sort(key=lambda r: (r["total_usd_value"] or 0), reverse=True)

    grand_total = sum(r["total_usd_value"] for r in rows if r["total_usd_value"] is not None)

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["token_symbol", "total_balance", "total_usd_value", "chains"])
        for r in rows:
            writer.writerow([
                r["token_symbol"],
                f"{r['total_balance']:.8f}",
                f"{r['total_usd_value']:.2f}" if r["total_usd_value"] is not None else "N/A",
                r["chains"],
            ])
        writer.writerow(["TOTAL", "", f"{grand_total:.2f}", ""])

    logger.info(f"Cross-chain CSV: {filepath}")
    return filepath
