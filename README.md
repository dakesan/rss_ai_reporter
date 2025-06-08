# RSS AI Reporter

科学論文ジャーナル（Nature、Science等）のRSSフィードを定期的に取得し、新着論文をGemini APIでサマライズしてSlackに通知するシステムです。

## 🚀 主要機能

### ✅ 基本機能（実装済み）
- **RSS取得**: Nature、ScienceのRSSフィードから最新論文を自動取得
- **論文詳細取得**: アブストラクト、著者情報、研究機関を含む詳細情報の取得
- **AI要約**: Gemini APIによる日本語での論文サマライズ（200-300文字）
- **Slack通知**: 毎日朝9時（JST）に最大10件の論文を通知
- **フィルタリング**: キーワードベースの論文フィルタリング機能

### ✅ 継続学習システム（Phase 6完了）
- **フィードバック収集**: Slackボタンによるリアルタイム評価収集
- **AI分析**: Gemini APIによるフィードバックパターン分析
- **自動フィルター更新**: AI分析結果に基づく自動フィルター改善
- **AWS Lambda統合**: サーバーレスフィードバック処理
- **GitHub Issues連携**: フィードバックデータの永続化

## 🛠️ セットアップ

### 1. 環境設定

```bash
git clone [your-repo]
cd rss_ai_reporter
```

### 2. 依存関係のインストール

```bash
uv venv
source .venv/bin/activate  # Linux/Mac
uv pip install -r requirements.txt
```

### 3. 環境変数の設定

`.env` ファイルを作成して以下を設定：

```bash
# Gemini API Configuration
GEMINI_API_KEY=your_gemini_api_key_here

# Slack Configuration
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# GitHub Configuration (自動更新用)
GITHUB_TOKEN=ghp_your_github_token_here
GITHUB_REPO=your_username/rss_ai_reporter

# Slack Signing Secret (フィードバック検証用)
SLACK_SIGNING_SECRET=your_slack_signing_secret_here
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