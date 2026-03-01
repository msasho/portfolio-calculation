"""
Playwright-based portfolio scanner.
Takes full-page screenshots of DeBank, Step Finance, Solscan, and Hyperliquid
for later image analysis.
"""
import os
import sys
import json
import time
import asyncio
from playwright.async_api import async_playwright

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WALLETS_FILE = os.path.join(SCRIPT_DIR, ".claude", "skills", "portfolio-checker", "assets", "wallets.json")
SCREENSHOT_DIR = os.path.join(SCRIPT_DIR, "output", "screenshots")

VIEWPORT = {"width": 1440, "height": 900}
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def load_wallets() -> dict:
    with open(WALLETS_FILE, "r") as f:
        return json.load(f)


async def slow_scroll(page, pause=2.0, scrolls=5):
    for _ in range(scrolls):
        await page.evaluate("window.scrollBy(0, window.innerHeight * 0.8)")
        await asyncio.sleep(pause)


async def scan_debank(page, address: str, idx: int):
    """Scan a single EVM wallet on DeBank."""
    short = address[:8]
    url = f"https://debank.com/profile/{address}"
    print(f"  [{idx}] DeBank: {short}... -> {url}")

    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(6)

    # Scroll to load all tokens and DeFi positions
    await slow_scroll(page, pause=2.5, scrolls=6)

    # Back to top for full page screenshot
    await page.evaluate("window.scrollTo(0, 0)")
    await asyncio.sleep(1)

    path = os.path.join(SCREENSHOT_DIR, f"debank_{short}.png")
    await page.screenshot(path=path, full_page=True)
    print(f"    -> Saved: {path}")
    return path


async def scan_step_finance(page, address: str, idx: int):
    """Scan Solana DeFi positions on Step Finance."""
    short = address[:8]
    url = f"https://app.step.finance/en/dashboard?watching={address}"
    print(f"  [{idx}] Step Finance: {short}... -> {url}")

    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(8)

    await slow_scroll(page, pause=2.0, scrolls=4)
    await page.evaluate("window.scrollTo(0, 0)")
    await asyncio.sleep(1)

    path = os.path.join(SCREENSHOT_DIR, f"step_{short}.png")
    await page.screenshot(path=path, full_page=True)
    print(f"    -> Saved: {path}")
    return path


async def scan_solscan(page, address: str, idx: int):
    """Scan Solana token balances on Solscan."""
    short = address[:8]
    url = f"https://solscan.io/account/{address}#portfolio"
    print(f"  [{idx}] Solscan: {short}... -> {url}")

    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(5)

    # Click Portfolio tab if not already active
    try:
        portfolio_tab = page.locator("button:has-text('Portfolio')")
        if await portfolio_tab.count() > 0:
            await portfolio_tab.first.click()
            await asyncio.sleep(3)
    except Exception:
        pass

    await slow_scroll(page, pause=1.5, scrolls=3)
    await page.evaluate("window.scrollTo(0, 0)")
    await asyncio.sleep(1)

    path = os.path.join(SCREENSHOT_DIR, f"solscan_{short}.png")
    await page.screenshot(path=path, full_page=True)
    print(f"    -> Saved: {path}")
    return path


async def scan_hyperliquid(page, address: str, idx: int):
    """Scan Hyperliquid portfolio page."""
    short = address[:8]
    url = f"https://app.hyperliquid.xyz/portfolio/{address}"
    print(f"  [{idx}] Hyperliquid: {short}... -> {url}")

    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(6)

    await slow_scroll(page, pause=2.0, scrolls=3)
    await page.evaluate("window.scrollTo(0, 0)")
    await asyncio.sleep(1)

    path = os.path.join(SCREENSHOT_DIR, f"hl_{short}.png")
    await page.screenshot(path=path, full_page=True)
    print(f"    -> Saved: {path}")
    return path


async def main():
    wallets = load_wallets()
    evm = wallets.get("evm", [])
    sol = wallets.get("solana", [])

    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    print(f"EVM wallets: {len(evm)}, Solana wallets: {len(sol)}")
    print(f"Screenshots dir: {SCREENSHOT_DIR}\n")

    # Determine which scans to run
    targets = sys.argv[1:] if len(sys.argv) > 1 else ["debank", "step", "solscan", "hyperliquid"]

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            viewport=VIEWPORT,
            user_agent=USER_AGENT,
            locale="en-US",
        )
        page = await context.new_page()

        all_screenshots = []

        # DeBank (EVM)
        if "debank" in targets and evm:
            print("=== DeBank (EVM Multi-Chain + DeFi) ===")
            for i, addr in enumerate(evm, 1):
                try:
                    path = await scan_debank(page, addr, i)
                    all_screenshots.append({"source": "debank", "wallet": addr, "path": path})
                except Exception as e:
                    print(f"    ERROR: {e}")
                if i < len(evm):
                    await asyncio.sleep(8)

        # Step Finance (Solana DeFi)
        if "step" in targets and sol:
            print("\n=== Step Finance (Solana DeFi) ===")
            for i, addr in enumerate(sol, 1):
                try:
                    path = await scan_step_finance(page, addr, i)
                    all_screenshots.append({"source": "step", "wallet": addr, "path": path})
                except Exception as e:
                    print(f"    ERROR: {e}")

        # Solscan (Solana tokens)
        if "solscan" in targets and sol:
            print("\n=== Solscan (Solana Tokens) ===")
            for i, addr in enumerate(sol, 1):
                try:
                    path = await scan_solscan(page, addr, i)
                    all_screenshots.append({"source": "solscan", "wallet": addr, "path": path})
                except Exception as e:
                    print(f"    ERROR: {e}")

        # Hyperliquid
        if "hyperliquid" in targets and evm:
            print("\n=== Hyperliquid ===")
            for i, addr in enumerate(evm, 1):
                try:
                    path = await scan_hyperliquid(page, addr, i)
                    all_screenshots.append({"source": "hyperliquid", "wallet": addr, "path": path})
                except Exception as e:
                    print(f"    ERROR: {e}")
                if i < len(evm):
                    await asyncio.sleep(5)

        await browser.close()

    # Save manifest
    manifest_path = os.path.join(SCREENSHOT_DIR, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(all_screenshots, f, indent=2)
    print(f"\nManifest saved: {manifest_path}")
    print(f"Total screenshots: {len(all_screenshots)}")


if __name__ == "__main__":
    asyncio.run(main())
