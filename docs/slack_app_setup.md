# Slack App Interactive Components 設定ガイド

RSS AI Reporterでフィードバックボタン機能を有効にするためのSlack App設定手順です。

## 前提条件

- 既存のSlack Appがある（RSS AI Reporter用）
- Incoming Webhooksが既に設定済み
- Slack Workspaceの管理者権限がある

## 1. Interactive Components の有効化

### 1.1 Slack API管理画面にアクセス
1. [Slack API](https://api.slack.com/apps) にアクセス
2. 既存のRSS AI Reporter Appを選択

### 1.2 Interactive Components を有効化
1. 左メニューから **「Interactive Components」** を選択
2. **「Interactivity」** をONに切り替え
3. **「Request URL」** に以下を設定：
   ```
   https://your-domain.com/slack/feedback
   ```
   ※ あなたのWebhookサーバーのURLに置き換えてください

### 1.3 設定保存
1. **「Save Changes」** をクリック

## 2. Request URL の設定

### 2.1 公開可能なURLの準備
フィードバックを受信するため、インターネットからアクセス可能なURLが必要です。

**オプション1: ngrok使用（開発・テスト用）**
```bash
# ngrokをインストール（初回のみ）
npm install -g ngrok
# または
brew install ngrok

# Webhookサーバーを起動
python src/webhook_server.py

# 別ターミナルでngrokを起動
ngrok http 5000
```
生成されたhttps URLを使用：`https://xxxxx.ngrok.io/slack/feedback`

**オプション2: クラウドサービス（本番用）**
- Heroku、Render、Railway等にデプロイ
- GitHub ActionsでAWS Lambda等にデプロイ
- Docker Containerとして運用

### 2.2 URL検証
1. Slack APIの管理画面でURLを設定
2. **「Verify」** ボタンをクリック
3. ✅ 緑色のチェックマークが表示されることを確認

## 3. OAuth Permissions の確認

### 3.1 必要な権限
左メニューの **「OAuth & Permissions」** で以下の権限があることを確認：

**Bot Token Scopes:**
- `chat:write` - メッセージ送信
- `incoming-webhook` - Webhook使用

**User Token Scopes:**
- 特に追加は不要

### 3.2 権限が不足している場合
1. 必要な権限を追加
2. **「Reinstall App」** をクリック
3. ワークスペースで再認証

## 4. 環境変数の設定

### 4.1 Slack Signing Secret の取得
1. Slack API管理画面の **「Basic Information」** を選択
2. **「App Credentials」** セクションを展開
3. **「Signing Secret」** をコピー

### 4.2 GitHub Token の設定
1. [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens) にアクセス
2. **「Generate new token (classic)」** をクリック
3. 以下の権限を選択：
   - `repo` - プライベートリポジトリアクセス
   - `public_repo` - パブリックリポジトリアクセス
4. トークンをコピー（一度しか表示されません）

### 4.3 環境変数設定例
```bash
# ローカル実行用
export SLACK_SIGNING_SECRET="your_signing_secret_here"
export GITHUB_TOKEN="ghp_your_github_token_here"
export GITHUB_REPO="username/rss_ai_reporter"

# 本番環境用 (.env ファイルまたはクラウド設定)
SLACK_SIGNING_SECRET=your_signing_secret_here
GITHUB_TOKEN=ghp_your_github_token_here
GITHUB_REPO=username/rss_ai_reporter
```

## 5. Webhookサーバーの起動

### 5.1 ローカル実行
```bash
# 依存関係インストール
pip install -r requirements.txt

# 環境変数設定
export SLACK_SIGNING_SECRET="your_secret"
export GITHUB_TOKEN="your_token"
export GITHUB_REPO="username/rss_ai_reporter"

# サーバー起動
python src/webhook_server.py
```

### 5.2 サーバー確認
```bash
# ヘルスチェック
curl http://localhost:5000/health

# 期待される応答例：
{
  "status": "ok",
  "service": "RSS AI Reporter Feedback Server",
  "github_token": "configured",
  "slack_secret": "configured"
}
```

## 6. テスト手順

### 6.1 フィードバックボタン付き通知送信
```bash
# 環境変数設定
export SLACK_WEBHOOK_URL="your_webhook_url"
export GEMINI_API_KEY="your_gemini_key"

# 3エントリテスト実行
python src/main.py --slack-test-3
```

### 6.2 フィードバック動作確認
1. Slackにフィードバックボタン付きメッセージが表示される
2. 👍または👎ボタンをクリック
3. エフェメラルメッセージ（本人のみ表示）でフィードバック受信確認
4. GitHubリポジトリにIssueが自動作成される
5. `data/feedback_log.jsonl`にローカルログが記録される

### 6.3 フィードバック統計確認
```bash
# 統計API確認
curl http://localhost:5000/slack/feedback/summary

# 期待される応答例：
{
  "total": 2,
  "interested": 1,
  "not_interested": 1,
  "articles": [...]
}
```

## 7. トラブルシューティング

### 7.1 よくある問題

**Request URL検証が失敗する**
- Webhookサーバーが起動しているか確認
- URLが公開アクセス可能か確認
- ファイアウォール設定の確認

**フィードバックボタンが表示されない**
- `--slack-test-3`フラグで実行しているか確認
- `enable_feedback=True`で通知しているか確認

**ボタンクリックが反応しない**
- Slack Signing Secretが正しく設定されているか確認
- Webhook サーバーのログでエラーを確認

**GitHub Issueが作成されない**
- GitHub Tokenの権限を確認
- リポジトリ名が正しいか確認
- GitHub APIレスポンスをログで確認

### 7.2 デバッグコマンド
```bash
# フィードバックハンドラー単体テスト
python src/feedback_handler.py

# Webhookサーバーログ確認
FLASK_DEBUG=true python src/webhook_server.py

# フィードバックログ確認
cat data/feedback_log.jsonl | jq .
```

## 8. 本番運用の考慮事項

### 8.1 セキュリティ
- HTTPS使用必須
- Slack Signing Secretによるリクエスト検証
- GitHub Token の安全な管理

### 8.2 可用性
- Webhookサーバーの冗長化
- ログローテーション設定
- モニタリングとアラート設定

### 8.3 スケーラビリティ
- 大量フィードバック時の処理性能
- GitHub API rate limit考慮
- ログストレージ容量管理

---

以上でSlack App Interactive Components の設定は完了です。
フィードバック機能が正常に動作することを確認してから、Phase 6-3（AI分析エンジン）に進んでください。