# Portfolio Calculation

複数チェーン・複数ウォレットの暗号資産ポートフォリオを集計するツール。
Playwright で DeBank のスクリーンショットを自動取得し、Jupiter / 取引所のスクショは手動配置。
Claude の画像認識でトークンデータを抽出し、CSV レポートを生成する。

## 対応チェーン

- **EVM**: Ethereum, Arbitrum, Optimism, Base, Avalanche, Sonic, HyperEVM (DeBank経由)
- **Solana** (Jupiter スクショを手動配置)
- **Hyperliquid** Spot / Perps (DeBank経由)

## セットアップ

```bash
# 依存パッケージのインストール
uv sync

# ブラウザのインストール
uv run python -m playwright install chromium

# ウォレット設定 (.env.example を参考に)
cp .env.example .env
# .env の EVM_WALLETS, SOLANA_WALLETS にアドレスを設定
```

## 使い方 (4フェーズ)

### Phase 1: DeBank 自動スクショ

```bash
uv run python .claude/skills/portfolio-scan/scripts/browser_scanner.py
```

`output/YYYYMMDD/screenshots/` に DeBank のスクリーンショットが保存される。

### Phase 2: 手動スクショ配置

Jupiter Portfolio (`jup.ag/portfolio/{address}`) や取引所の残高画面のスクリーンショットを
同じ `screenshots/` フォルダに PNG で配置する。

### Phase 3 & 4: 画像解析・レポート生成

Claude Code のスキル（`ポートフォリオ集計して`）を実行すると、
全スクリーンショットから画像認識でデータを抽出し、以下の CSV を生成する:

- `portfolio_by_token.csv` — トークン別集計
- `portfolio_by_exposure.csv` — カテゴリ別エクスポージャー (USD Stables, ETH, BTC, SOL, Others)
