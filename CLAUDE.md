# RSS論文サマライザー

## プロジェクト概要
科学論文ジャーナル（Nature、Science等）のRSSフィードを定期的に取得し、新着論文をGemini APIでサマライズしてSlackに通知するシステムを構築してください。

## 主要機能

### 1. RSS取得機能
- Nature、ScienceのRSSフィードから最新論文リストを取得
- 前回チェック時点との差分を検出
- チェックポイントをJSONファイルで管理
- RSSに十分な情報がない場合は論文ページから詳細を取得
  - アブストラクト（要約）
  - 著者情報
  - 研究機関
  - キーワード

### 2. 論文サマライズ機能
- Gemini API（無料枠）を使用して各論文を要約
- 1論文あたり200-300文字程度の日本語サマリーを生成
- 論文の重要性や革新性についてのコメントを含める

### 3. Slack通知機能
- 毎日朝9時（JST）に実行
- 1回の通知で最大10件の論文を含める
- 大量の論文がある場合は複数日に分けて通知
- 以下の形式でメッセージを作成：
  ```
  📚 今日の論文レポート（Nature & Science）
  
  1️⃣ [論文タイトル]
  👥 著者グループ名
  📝 [200-300文字の要約。どのような研究で、何が重要かを説明]
  🔗 [論文へのリンク]
  
  2️⃣ ...
  ```

### 4. フィルタリング機能
- キーワードベースのフィルタリング（含む/含まない）
- 設定はJSONファイルで管理
- 例：
  ```json
  {
    "include": ["CRISPR", "quantum", "AI"],
    "exclude": ["review", "correction", "retraction"]
  }
  ```

## 技術仕様

### GitHub Actions
- 実行スケジュール：毎日朝9時（JST）
- cronで設定：`0 0 * * *`（UTC）

### データ管理
以下のJSONファイルをリポジトリ内で管理：
1. `last_check.json` - 前回チェック時の論文IDと日時
2. `queue.json` - 未処理論文のキュー（大量論文の分割処理用）
3. `filter_config.json` - フィルタリング設定

### APIキー管理
GitHub Secretsに以下を設定：
- `GEMINI_API_KEY` - Gemini APIキー
- `SLACK_WEBHOOK_URL` - Slack Webhook URL

## ディレクトリ構造
```
/
├── .github/
│   └── workflows/
│       └── summarize.yml    # GitHub Actions設定
├── src/
│   ├── rss_fetcher.py      # RSS取得
│   ├── content_fetcher.py  # 論文詳細取得
│   ├── summarizer.py       # Gemini APIでサマライズ
│   ├── slack_notifier.py   # Slack通知
│   └── main.py             # メイン処理
├── data/
│   ├── last_check.json     # チェックポイント
│   ├── queue.json          # 未処理キュー
│   └── filter_config.json  # フィルタ設定
├── requirements.txt        # Python依存関係
└── README.md              # プロジェクト説明
```

## 実装の注意点

1. **コンテンツ取得**
   - NatureとScienceでは論文ページの構造が異なるため、それぞれに対応
   - アブストラクトが取得できない場合は、タイトルと入手可能な情報でサマライズ
   - robots.txtを尊重し、適切な間隔でアクセス

2. **エラーハンドリング**
   - RSS取得失敗、API制限、ネットワークエラーに対応
   - エラー時もSlackに通知

3. **レート制限対策**
   - Gemini API無料枠の制限を考慮
   - 必要に応じて処理を分割
   - 論文ページへのアクセスは1秒以上の間隔を空ける

3. **Slack Webhook設定手順**
   - Slack Appの作成方法を説明
   - Incoming Webhooksの設定方法を記載
   - テスト用のcurlコマンド例：
     ```bash
     curl -X POST -H 'Content-type: application/json' \
     --data '{"text":"テストメッセージ"}' \
     YOUR_WEBHOOK_URL
     ```

4. **拡張性**
   - 新しいジャーナルの追加が容易な設計
   - フィルタリングルールの柔軟な設定

## セットアップ手順

### 1. Slack Webhook URLの取得
1. [Slack API](https://api.slack.com/apps)にアクセス
2. 「Create New App」→「From scratch」を選択
3. App名（例：論文サマライザー）とワークスペースを選択
4. 左メニューから「Incoming Webhooks」を選択
5. 「Activate Incoming Webhooks」をONにする
6. 「Add New Webhook to Workspace」をクリック
7. 投稿先のチャンネルを選択（例：#論文-通知）
8. 生成されたWebhook URL（`https://hooks.slack.com/services/...`）をコピー

### 2. Gemini APIキーの取得
1. [Google AI Studio](https://makersuite.google.com/app/apikey)にアクセス
2. 「Get API key」をクリック
3. 生成されたAPIキーをコピー

### 3. GitHub Secretsの設定
1. GitHubリポジトリの「Settings」→「Secrets and variables」→「Actions」
2. 「New repository secret」で以下を追加：
   - Name: `SLACK_WEBHOOK_URL`、Value: Slackで取得したWebhook URL
   - Name: `GEMINI_API_KEY`、Value: Geminiで取得したAPIキー

### 4. リポジトリのセットアップ
```bash
git clone [your-repo]
cd [your-repo]
pip install -r requirements.txt
```

### 5. 初回実行とテスト
```bash
# ローカルでテスト（環境変数を設定）
export SLACK_WEBHOOK_URL="your-webhook-url"
export GEMINI_API_KEY="your-api-key"
python src/main.py --test
```

## 使用する主なライブラリ
- `feedparser` - RSS解析
- `beautifulsoup4` - HTMLパース（論文詳細取得）
- `requests` - HTTP通信
- `google-generativeai` - Gemini API
- `json`, `datetime` - データ管理
