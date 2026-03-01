# Portfolio Calculation

複数チェーン・複数ウォレットの暗号資産ポートフォリオを集計するツール。
Playwrightでポートフォリオサイトのスクリーンショットを取得し、画像認識で残高・ポジションを抽出する。

## 対応チェーン

- **EVM**: Ethereum, Arbitrum, Optimism, Base, Polygon, BNB Chain, Avalanche (DeBank経由)
- **Solana** (Solscan / Step Finance経由)
- **Hyperliquid** Spot / Perps

## セットアップ

```bash
# 依存パッケージのインストール
pip install -r requirements.txt

# ブラウザのインストール
playwright install chromium

# 環境変数の設定
cp .env.example .env
# .env を編集してウォレットアドレスを設定
```

## 使い方

### 1. スクリーンショット取得

```bash
python browser_scanner.py [targets...]
```

DeBank / Solscan / Step Finance / Hyperliquid のページをPlaywrightでスクリーンショット取得する。ターゲットを指定しない場合は全サイトをスキャン。

```bash
# 例: DeBankとHyperliquidのみ
python browser_scanner.py debank hyperliquid
```

スクリーンショットは `output/screenshots/` に保存される。

### 2. レポート生成

```bash
python output/generate_report.py
```

スクリーンショットから抽出したデータを元に、CSV + XLSXレポートを生成する。

**出力ファイル** (`output/`):
- `portfolio_detail.csv` — 全トークン明細
- `portfolio_summary.csv` — トークン別集計
- `portfolio_report.xlsx` — ウォレット別・チェーン別・Top10のレポート

## 設定

`.env` でウォレットアドレスを設定:

```
EVM_WALLETS=0xABC...,0xDEF...      # カンマ区切りで複数指定
SOLANA_WALLETS=SoLaNa1...,SoLaNa2...
DUST_THRESHOLD_USD=1.0              # この金額以下のトークンを除外
```