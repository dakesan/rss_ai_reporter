# RSS論文サマライザー

科学論文ジャーナル（Nature、Science）のRSSフィードから新着論文を取得し、Gemini APIで日本語サマリーを生成してSlackに通知するシステムです。

## 機能

- 📰 Nature・ScienceのRSSフィードから新着論文を自動取得
- 🔍 論文ページから詳細情報（アブストラクト、著者、研究機関等）を抽出
- 🤖 Gemini API（無料枠）を使用した日本語要約生成
- 💬 Slackへの自動通知（毎日朝9時JST）
- 🔧 キーワードベースのフィルタリング機能
- 📋 大量論文の分割処理（1日最大10件）

## セットアップ

### 1. リポジトリのクローン

```bash
git clone [your-repository-url]
cd rss_ai_reporter
```

### 2. 必要なAPIキーの取得

#### Slack Webhook URL
1. [Slack API](https://api.slack.com/apps)にアクセス
2. 「Create New App」→「From scratch」を選択
3. App名とワークスペースを選択
4. 「Incoming Webhooks」を有効化
5. 「Add New Webhook to Workspace」で通知先チャンネルを選択
6. 生成されたWebhook URLをコピー

#### Gemini API Key
1. [Google AI Studio](https://makersuite.google.com/app/apikey)にアクセス
2. 「Get API key」をクリック
3. 生成されたAPIキーをコピー

### 3. GitHub Secretsの設定

リポジトリの「Settings」→「Secrets and variables」→「Actions」で以下を追加：
- `SLACK_WEBHOOK_URL`: SlackのWebhook URL
- `GEMINI_API_KEY`: Gemini APIキー

### 4. ローカルテスト

```bash
# 環境変数を設定
export SLACK_WEBHOOK_URL="your-webhook-url"
export GEMINI_API_KEY="your-api-key"

# 依存関係インストール
pip install -r requirements.txt

# テストモードで実行（Slack通知なし）
python src/main.py --test
```

## 設定

### フィルタリング設定

`data/filter_config.json`でキーワードフィルタを設定できます：

```json
{
  "include": ["CRISPR", "quantum", "AI"],
  "exclude": ["review", "correction", "retraction"]
}
```

- `include`: これらのキーワードを含む論文のみを通知
- `exclude`: これらのキーワードを含む論文を除外

### 実行スケジュール

`.github/workflows/summarize.yml`でスケジュールを変更できます。
デフォルトは毎日朝9時（JST）です。

## ディレクトリ構造

```
.
├── .github/
│   └── workflows/
│       └── summarize.yml       # GitHub Actions設定
├── src/
│   ├── rss_fetcher.py         # RSS取得
│   ├── content_fetcher.py     # 論文詳細取得
│   ├── summarizer.py          # Gemini APIサマライズ
│   ├── slack_notifier.py      # Slack通知
│   └── main.py                # メイン処理
├── data/
│   ├── last_check.json        # チェックポイント
│   ├── queue.json             # 未処理キュー
│   └── filter_config.json     # フィルタ設定
├── requirements.txt           # Python依存関係
├── README.md                  # このファイル
└── CLAUDE.md                  # プロジェクト仕様

```

## トラブルシューティング

### エラーが発生する場合

1. **API制限エラー**: Gemini APIの無料枠制限に達した可能性があります
2. **RSS取得エラー**: ネットワーク接続を確認してください
3. **Slack通知エラー**: Webhook URLが正しいか確認してください

### ログの確認

GitHub Actionsの実行ログで詳細なエラー情報を確認できます。

## ライセンス

MIT License