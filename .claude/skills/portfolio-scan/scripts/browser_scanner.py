"""
Playwright-based portfolio scanner.
Takes full-page screenshots of DeBank for later image analysis by Claude.

Usage:
    python browser_scanner.py

Notes:
    - DeBank: headless (CAPTCHA なし)
    - Jupiter / 取引所: 手動でスクリーンショットを配置

Prerequisites:
    pip install playwright
    python -m playwright install chromium
"""
import os
import json
import asyncio
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

# Load .env file (simple parser, no external dependency)
WORKSPACE = Path(__file__).resolve().parent.parent.parent.parent.parent
_env_file = WORKSPACE / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# Output goes to workspace output/YYYYMMDD/screenshots/
DATE_STR = datetime.now().strftime("%Y%m%d")
OUTPUT_DIR = WORKSPACE / "output" / DATE_STR
SCREENSHOT_DIR = OUTPUT_DIR / "screenshots"

VIEWPORT = {"width": 1440, "height": 900}
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def load_wallets() -> dict:
    """Load wallet addresses from environment variables."""
    evm_raw = os.environ.get("EVM_WALLETS", "")
    sol_raw = os.environ.get("SOLANA_WALLETS", "")
    evm = [a.strip() for a in evm_raw.split(",") if a.strip()]
    sol = [a.strip() for a in sol_raw.split(",") if a.strip()]
    if not evm and not sol:
        raise SystemExit("ERROR: EVM_WALLETS / SOLANA_WALLETS が .env に設定されていません")
    return {"evm": evm, "solana": sol}


async def slow_scroll(page, pause=2.0, scrolls=5):
    """Scroll down slowly to trigger lazy-loading content."""
    for _ in range(scrolls):
        await page.evaluate("window.scrollBy(0, window.innerHeight * 0.8)")
        await asyncio.sleep(pause)


async def save_screenshot(page, name: str, full_page=True) -> str:
    """Save screenshot and return the file path."""
    path = str(SCREENSHOT_DIR / f"{name}.png")
    await page.screenshot(path=path, full_page=full_page)
    print(f"    -> {path}")
    return path


# ── DeBank (EVM multi-chain + DeFi) ──────────────────────────────

async def scan_debank(page, address: str, idx: int, total: int) -> list[dict]:
    """
    Scan a single EVM wallet on DeBank.
    DeBank shows all chains + DeFi positions on one page.
    """
    short = address[:8]
    url = f"https://debank.com/profile/{address}"
    print(f"  [{idx}/{total}] DeBank: {short}...")

    screenshots = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(6)

        # Scroll to load all tokens and DeFi positions
        await slow_scroll(page, pause=2.5, scrolls=8)

        # Back to top for full page screenshot
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(1)

        path = await save_screenshot(page, f"debank_{short}")
        screenshots.append({
            "source": "debank", "wallet": address, "path": path,
            "type": "evm_full", "status": "ok"
        })
    except Exception as e:
        error_msg = str(e)[:120]
        print(f"    ERROR: {error_msg}")
        try:
            path = await save_screenshot(page, f"debank_{short}_error", full_page=False)
            screenshots.append({
                "source": "debank", "wallet": address, "path": path,
                "type": "evm_full", "status": "error", "error": error_msg
            })
        except Exception:
            screenshots.append({
                "source": "debank", "wallet": address, "path": "",
                "type": "evm_full", "status": "failed", "error": error_msg
            })

    return screenshots


# ── Main ──────────────────────────────────────────────────────────

async def main():
    wallets = load_wallets()
    evm = wallets.get("evm", [])

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"EVM wallets: {len(evm)}")
    print(f"Screenshots: {SCREENSHOT_DIR}\n")

    async with async_playwright() as p:
        all_screenshots = []

        # DeBank: headless で一括スキャン
        if evm:
            print("=== DeBank (EVM Multi-Chain + DeFi) ===")
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context(
                viewport=VIEWPORT, user_agent=USER_AGENT, locale="en-US",
            )
            page = await context.new_page()

            for i, addr in enumerate(evm, 1):
                results = await scan_debank(page, addr, i, len(evm))
                all_screenshots.extend(results)
                if i < len(evm):
                    await asyncio.sleep(8)

            await browser.close()

    # Save manifest
    manifest_path = str(SCREENSHOT_DIR / "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(all_screenshots, f, indent=2)

    ok = sum(1 for s in all_screenshots if s["status"] == "ok")
    err = sum(1 for s in all_screenshots if s["status"] != "ok")
    print(f"\nDone: {ok} ok, {err} errors")
    print(f"Manifest: {manifest_path}")
    print(f"OUTPUT_DIR={OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
