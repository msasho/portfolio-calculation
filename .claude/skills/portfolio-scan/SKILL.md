---
name: portfolio-scan
description: |
  スクリーンショットから資産情報を読み取り、ポートフォリオレポートを生成する。
  Phase 1: Playwright で DeBank のスクリーンショットを自動取得
  Phase 2: ユーザーが Jupiter / 取引所 / 証券口座等のスクリーンショットを手動配置
  Phase 3: Claude 画像認識で全画像から資産データを読み取り、raw_data.md に記録
  Phase 4: カテゴリ分類 → 2種の CSV を出力 (銘柄別 + エクスポージャー別)
  MANDATORY TRIGGERS: portfolio, wallet, asset check, balance check, crypto balance, token balance,
  資産計算, ポートフォリオ, ウォレット残高, 残高チェック, DeFi, 集計, 資産集計
---

# Portfolio Scan

ウォレットの全資産（DeFiポジション含む）をスキャンし、CSV にまとめる。

## アーキテクチャ

5フェーズで動作する:

1. **DeBank 自動スクショ** — Playwright で EVM ウォレットのスクリーンショットを撮影
1.5. **取引所 API 取得** — bitbank / GMO Coin の残高を API で自動取得（キー設定時のみ）
2. **手動スクショ配置** — ユーザーが Jupiter 等のスクリーンショットを同フォルダに配置
3. **画像解析** — Claude の画像認識でスクリーンショットからトークンデータを抽出 + API データを統合
4. **カテゴリ分類・CSV出力** — トークン別集計 + カテゴリ別エクスポージャーの2種 CSV を生成

## Prerequisites

- `.env` に `EVM_WALLETS` / `SOLANA_WALLETS` が設定されていること（カンマ区切り）

なければ `.env.example` を参考にユーザーに設定を依頼。

```
EVM_WALLETS=0xABC...,0xDEF...
SOLANA_WALLETS=SoLaNa1...
```

## Phase 1: DeBank 自動スクショ

### セットアップ

```bash
uv sync                                    # 依存パッケージをインストール
uv run python -m playwright install chromium
```

### 実行

```bash
uv run python .claude/skills/portfolio-scan/scripts/browser_scanner.py
```

スクリプトは `output/YYYYMMDD/screenshots/` にスクリーンショットと `manifest.json` を保存する。
最終行に `OUTPUT_DIR=output/YYYYMMDD` を出力するので、この値を後続フェーズで使用する。

### データソース

| Source | URL | 対象 | データ内容 | ブラウザモード |
|--------|-----|------|-----------|---------------|
| **DeBank** | `debank.com/profile/{address}` | EVM + Hyperliquid | 全チェーンのトークン残高 + DeFiポジション（LP, staking, lending）+ Hyperliquid spot/perp | headless |

**Hyperliquid は DeBank でカバーされるため個別スキャン不要。**

### Phase 1 がうまくいかない場合

- **プロキシ制限** (`net::ERR_EMPTY_RESPONSE`): VM環境のプロキシがブロックしている場合、ローカルで実行する

## Phase 1.5: 取引所 API 取得

bitbank / GMO Coin の API キーが `.env` に設定されている場合、API 経由で残高を自動取得する。

### 実行

```bash
uv run python .claude/skills/portfolio-scan/scripts/exchange_fetcher.py
```

- API キーが設定されている取引所のみ取得（未設定の取引所はスキップ）
- `output/YYYYMMDD/exchange_data.md` に raw_data.md と同じマークダウンテーブル形式で保存
- Phase 3 で `exchange_data.md` の内容を `raw_data.md` にそのままコピーする

### 必要な環境変数

```
BITBANK_API_KEY=...
BITBANK_API_SECRET=...
GMOCOIN_API_KEY=...
GMOCOIN_API_SECRET=...
```

## Phase 2: 手動スクショ配置

Phase 1 / 1.5 完了後、ユーザーに以下を依頼する。
**Phase 1.5 で API 取得できた取引所はスクリーンショット不要。**

> DeBank スクリーンショット取得が完了しました。
> {API で取得済みの取引所があれば「bitbank / GMO Coin は API で取得済みです。」と記載}
> 以下のスクリーンショットを `output/YYYYMMDD/screenshots/` フォルダに配置してください:
>
> - **Jupiter Portfolio** (`jup.ag/portfolio/{solana_address}`) のスクリーンショット
> - **取引所の残高画面**（API 未設定の取引所があれば）のスクリーンショット
>
> ファイル名や形式は問いません。配置が完了したら教えてください。

ユーザーの確認を待ってから Phase 2.5 に進む。

### Phase 2.5: 預金口座の確認

手動スクショ配置後、ユーザーに預金口座（銀行口座）の残高を集計に含めるか確認する。

> 預金口座の残高も集計に含めますか？
> 含める場合、各口座の銀行名と残高を教えてください（例: 楽天銀行 150万円、住信SBI 80万円）。
> スクリーンショットでも、テキスト入力でもOKです。

- テキスト入力の場合: 銀行名と残高を `output/YYYYMMDD/raw_data.md` の Phase 3 で直接記録する
- スクショ配置の場合: `output/YYYYMMDD/screenshots/` に配置後、`bank_{銀行名}.png` にリネームする
- 含めない場合: そのまま Phase 3 に進む

ユーザーの確認を待ってから Phase 3 に進む。

### 配置画像のリネーム

ユーザーが配置した画像は、Phase 3 の前に以下の命名規則でリネームする:

- `jupiter_{address先頭8文字}.png` — Jupiter スクショ
- `{取引所名}_{連番}.png` — 取引所スクショ（例: `bybit_1.png`, `binance_1.png`）

画像の内容（ファイル名やスクショの見た目）からソースを判別してリネームする。
判別できない場合は `manual_{連番}.png` とする。

## Phase 3: 画像解析 → 生データ記録

`output/YYYYMMDD/screenshots/` 内の全画像ファイルを **Read ツール** で読み込み、
読み取った情報を **`output/YYYYMMDD/raw_data.md`** にマークダウン形式で記録する。

**API データの統合**: `output/YYYYMMDD/exchange_data.md` が存在する場合、
その内容を `raw_data.md` の末尾にそのままコピーする（API で取得済みの取引所のスクリーンショットは読み取り不要）。

### 基本方針

- 画像に表示されている資産情報を **漏れなく** 読み取る
- この段階では構造化（CSV化）しない。後続の Phase 4 で集計するための「生データ」として記録する
- 資産の種別は問わない（暗号資産、株式、投信、現金、ポイント等なんでも可）
- 画像から読み取れる情報はなるべくそのまま記録する（数値の丸めや変換をしない）

### 画像ごとの記録フォーマット

画像1枚につき1セクションを作成する:

```markdown
## {ファイル名}

- **ソース**: {判別したサービス名。例: DeBank, Jupiter, Bybit, SBI証券, 楽天証券 等}
- **読み取り日**: {スクショの日付が分かれば。不明なら "不明"}
- **サマリー**: {画面に表示されている合計額があれば}

### 保有資産

| 銘柄/シンボル | 名称 | 数量 | 単価 | 評価額 | 通貨 | 備考 |
|---|---|---|---|---|---|---|
| ETH | Ethereum | 0.51 | $1,925 | $981.87 | USD | Arbitrum chain |
| AAPL | Apple Inc. | 10 | ¥32,500 | ¥325,000 | JPY | 特定口座 |

### DeFi / その他ポジション

（LP、ステーキング、信用取引、オプション等、単純保有でないものがあれば）

| プロトコル/サービス | ポジション内容 | 評価額 | 通貨 | 備考 |
|---|---|---|---|---|
| Aave | USDC Supply | $5,000 | USD | Arbitrum |

### 読み取りメモ

- {画像が見切れている、一部不鮮明、等の注意事項があれば}
```

### 読み取りのヒント（暗号資産）

- **DeBank**: ページ上部の Total Net Worth、Wallet セクション（チェーン別トークン一覧）、Protocol セクション（DeFi ポジション）
- **Jupiter**: ヘッダーの Net Worth / Positions Value、Tokens 一覧、Positions 一覧
- **取引所** (Bybit, Binance 等): 表示されている銘柄・数量・評価額

### スパムフィルタリング（暗号資産のみ）

暗号資産のスクショでは、トークン名に以下を含むものは除外する（エアドロップ詐欺）:
`claim`, `airdrop`, `visit`, `redeem`, `t.me`, `t.ly`, `.com`, `.xyz`, `.io` 等

残高 0 のトークンと USD $1.00 未満（dust）も除外。

### 口座情報メモ

- **楽天証券（特定口座）**: 保有銘柄は全て **eMAXIS Slim 全世界株式（オール・カントリー）＝オルカン**。CSV の symbol は `楽天証券`、name は `Japanese Securities (Rakuten Sec)` として集計する。

## Phase 4: 集計・CSV 出力

`raw_data.md` を入力として、集計・CSV 出力を行う。

### 通貨の統一

- 評価額の通貨が混在する場合（USD, JPY 等）、すべて **JPY 建て（円建て）** に換算して集計する
- USD → JPY の為替レートは **Web 検索**（WebSearch ツール）で当日のレートを取得して使用する

### カテゴリマッピング

`assets/token_categories.json` を読み込み、各銘柄をカテゴリに分類する。
大文字小文字を区別しない（case-insensitive）。

**未知銘柄の扱い**: どのカテゴリにもマッチしない銘柄が見つかった場合、
自動で Others に入れず **ユーザーに分類先を確認する**（AskUserQuestion ツールを使用）。
回答を得たら `assets/token_categories.json` を更新し、次回以降は同じ質問をしない。

### CSV 出力

2つの CSV を `output/YYYYMMDD/` に出力する:

**`portfolio_by_asset.csv`** — 銘柄別集計:
```csv
symbol,name,total_amount,total_jpy_value,percentage
USDC,USD Coin,12030.02,"1,804,567",69.3%
ETH,Ethereum,0.51,"147,279",5.7%
```

**`portfolio_by_exposure.csv`** — カテゴリ別エクスポージャー:
```csv
category,total_jpy_value,percentage,assets_included
USD Stables,"2,381,174",87.1%,"USDC(¥1,804,275), FEUSD(¥461,900)"
ETH,147279,5.7%,"ETH(¥147,279)"
```

### ユーザーへのレポート

CSV 出力後、以下を報告する:

- ポートフォリオ総額（JPY）
- カテゴリ別エクスポージャー（割合付き）
- Top 10 保有銘柄
- CSV ファイルパス