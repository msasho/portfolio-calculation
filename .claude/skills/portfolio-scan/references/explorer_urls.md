# Explorer URL Reference

## Primary Data Sources

### DeBank (EVM Multi-Chain + DeFi) — 自動スキャン

URL: `https://debank.com/profile/{address}`

All EVM chains visible in single page view:
- Ethereum, Arbitrum, Optimism, Base, Avalanche, Sonic, HyperEVM
- Wallet section: chain-by-chain token balances (symbol, balance, USD price, USD value)
- Protocol section: DeFi positions per protocol (LP, staking, lending, farming)
- Total Net Worth displayed at page top
- **Hyperliquid は DeBank でカバーされるため個別スキャン不要**

Access: Playwright headless で取得可能（CAPTCHA なし）

### Jupiter Portfolio (Solana + DeFi) — 手動スクショ

URL: `https://jup.ag/portfolio/{address}`

- Net Worth (total) and Positions Value (DeFi total) in header
- Tokens: SOL + all SPL tokens (symbol, amount, price, value)
- Positions: DeFi positions across protocols (Meteora, Kamino, Orca, Raydium, etc.)
- **Cloudflare CAPTCHA が頻発するため、ユーザーが手動でスクリーンショットを取得して配置する**

### 取引所 — 手動スクショ

Bybit, Binance 等の取引所残高画面もスクリーンショットで対応。
ユーザーが手動でスクショを撮影し、同じ screenshots フォルダに配置する。

## Fallback / Supplementary Explorers

| Chain | Explorer | URL Pattern |
|-------|----------|-------------|
| Ethereum | Etherscan | `https://etherscan.io/address/{address}` |
| Arbitrum | Arbiscan | `https://arbiscan.io/address/{address}` |
| Optimism | OP Etherscan | `https://optimistic.etherscan.io/address/{address}` |
| Base | BaseScan | `https://basescan.org/address/{address}` |
| Avalanche | Snowtrace | `https://snowtrace.io/address/{address}` |
| Sonic | Sonic Explorer | `https://sonicscan.org/address/{address}` |
| Solana | Solscan | `https://solscan.io/account/{address}#portfolio` |
| Solana | Solana Explorer | `https://explorer.solana.com/address/{address}` |

## Access Notes

- DeBank: Playwright headless で取得可能。CAPTCHA なし。
- Jupiter: Cloudflare CAPTCHA が頻発。手動スクショで対応。
- Solscan: Solana トークンデータのフォールバックとして使用可能。