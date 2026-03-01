"""
Fetch exchange balances via REST API (bitbank / GMO Coin).

Outputs a markdown file in the same format as raw_data.md sections,
so it can be directly incorporated during Phase 3.

Usage:
    python exchange_fetcher.py

Environment variables (set in .env):
    BITBANK_API_KEY / BITBANK_API_SECRET   — bitbank
    GMOCOIN_API_KEY / GMOCOIN_API_SECRET   — GMO Coin

If keys are not set, that exchange is silently skipped.
"""

import hashlib
import hmac
import json
import os
import time
import urllib.request
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WORKSPACE = Path(__file__).resolve().parent.parent.parent.parent.parent
DATE_STR = datetime.now().strftime("%Y%m%d")
DATE_LABEL = datetime.now().strftime("%Y-%m-%d")
OUTPUT_DIR = WORKSPACE / "output" / DATE_STR

# Load .env (same approach as browser_scanner.py)
_env_file = WORKSPACE / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

DUST_THRESHOLD_JPY = 1.0


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------


def _api_get(url: str, headers: dict) -> dict:
    """Send GET request and return parsed JSON."""
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


# ---------------------------------------------------------------------------
# bitbank
# ---------------------------------------------------------------------------

BITBANK_NAMES = {
    "jpy": "Japanese Yen",
    "btc": "Bitcoin",
    "eth": "Ethereum",
    "xrp": "Ripple",
    "ltc": "Litecoin",
    "bcc": "Bitcoin Cash",
    "mona": "MonaCoin",
    "xlm": "Stellar",
    "bat": "Basic Attention Token",
    "omg": "OMG Network",
    "xym": "Symbol",
    "link": "Chainlink",
    "mkr": "Maker",
    "bnb": "BNB",
    "matic": "Polygon",
    "pol": "Polygon",
    "dot": "Polkadot",
    "doge": "Dogecoin",
    "sol": "Solana",
    "ada": "Cardano",
    "avax": "Avalanche",
    "axs": "Axie Infinity",
    "flr": "Flare",
    "sand": "The Sandbox",
    "ape": "ApeCoin",
    "gala": "Gala",
    "chz": "Chiliz",
    "oasys": "Oasys",
    "mana": "Decentraland",
    "arb": "Arbitrum",
    "op": "Optimism",
    "dai": "Dai",
    "klay": "Klaytn",
    "imx": "Immutable X",
    "mask": "Mask Network",
    "usdc": "USD Coin",
    "shib": "Shiba Inu",
    "aave": "Aave",
    "pendle": "Pendle",
}


def fetch_bitbank() -> str | None:
    """Fetch bitbank balances. Returns markdown or None if keys not set."""
    api_key = os.environ.get("BITBANK_API_KEY", "").strip()
    api_secret = os.environ.get("BITBANK_API_SECRET", "").strip()
    if not api_key or not api_secret:
        return None

    path = "/v1/user/assets"
    nonce = str(int(time.time() * 1000))
    message = nonce + path
    signature = hmac.new(
        api_secret.encode(), message.encode(), hashlib.sha256
    ).hexdigest()

    data = _api_get(
        f"https://api.bitbank.cc{path}",
        {
            "ACCESS-KEY": api_key,
            "ACCESS-NONCE": nonce,
            "ACCESS-SIGNATURE": signature,
        },
    )

    if data.get("success") != 1:
        raise RuntimeError(f"bitbank API error: {data}")

    assets = data["data"]["assets"]
    rows: list[str] = []
    for a in assets:
        symbol = a["asset"].upper()
        amount = float(a["onhand_amount"])
        if amount <= 0:
            continue
        name = BITBANK_NAMES.get(a["asset"], symbol)
        if symbol == "JPY":
            jpy_val = f"¥{amount:,.0f}"
            rows.append(
                f"| {symbol} | {name} | {amount:,.4f} | - | {jpy_val} | JPY | 現金残高 |"
            )
        else:
            rows.append(
                f"| {symbol} | {name} | {amount} | - | - | - | API 取得 |"
            )

    if not rows:
        return None

    table = "\n".join(rows)
    return f"""## bitbank_api

- **ソース**: bitbank（API）
- **取得日**: {DATE_LABEL}

### 保有資産

| 銘柄/シンボル | 名称 | 数量 | 単価 | 評価額 | 通貨 | 備考 |
|---|---|---|---|---|---|---|
{table}
"""


# ---------------------------------------------------------------------------
# GMO Coin
# ---------------------------------------------------------------------------


def fetch_gmocoin() -> str | None:
    """Fetch GMO Coin balances. Returns markdown or None if keys not set."""
    api_key = os.environ.get("GMOCOIN_API_KEY", "").strip()
    api_secret = os.environ.get("GMOCOIN_API_SECRET", "").strip()
    if not api_key or not api_secret:
        return None

    path = "/v1/account/assets"
    timestamp = str(int(time.time() * 1000))
    message = timestamp + "GET" + path
    signature = hmac.new(
        api_secret.encode(), message.encode(), hashlib.sha256
    ).hexdigest()

    data = _api_get(
        f"https://api.coin.z.com/private{path}",
        {
            "API-KEY": api_key,
            "API-TIMESTAMP": timestamp,
            "API-SIGN": signature,
        },
    )

    if data.get("status") != 0:
        raise RuntimeError(f"GMO Coin API error: {data}")

    rows: list[str] = []
    for a in data["data"]:
        symbol = a["symbol"]
        amount = float(a["amount"])
        if amount <= 0:
            continue
        rate = float(a.get("conversionRate", 0))
        jpy_val = amount * rate if rate else 0

        if symbol == "JPY":
            rows.append(
                f"| {symbol} | Japanese Yen | {amount:,.0f} | - | ¥{jpy_val:,.0f} | JPY | 現金残高 |"
            )
        elif jpy_val >= DUST_THRESHOLD_JPY:
            price_str = f"¥{rate:,.0f}" if rate else "-"
            rows.append(
                f"| {symbol} | {symbol} | {amount} | {price_str} | ¥{jpy_val:,.0f} | JPY | API 取得 |"
            )

    if not rows:
        return None

    table = "\n".join(rows)
    return f"""## gmocoin_api

- **ソース**: GMOコイン（API）
- **取得日**: {DATE_LABEL}

### 保有資産

| 銘柄/シンボル | 名称 | 数量 | 単価 | 評価額 | 通貨 | 備考 |
|---|---|---|---|---|---|---|
{table}
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    sections: list[str] = []
    fetched: list[str] = []

    print("=== Exchange API Fetcher ===\n")

    for name, fetch_fn in [("bitbank", fetch_bitbank), ("GMO Coin", fetch_gmocoin)]:
        try:
            result = fetch_fn()
            if result is None:
                print(f"  {name}: skipped (API key not set)")
            else:
                sections.append(result)
                fetched.append(name)
                print(f"  {name}: OK")
        except Exception as e:
            print(f"  {name}: ERROR - {e}")

    if not sections:
        print("\nNo exchange data fetched.")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "exchange_data.md"
    out_path.write_text("\n".join(sections))

    print(f"\nFetched: {', '.join(fetched)}")
    print(f"Output: {out_path}")
    print(f"OUTPUT_DIR={OUTPUT_DIR}")


if __name__ == "__main__":
    main()
