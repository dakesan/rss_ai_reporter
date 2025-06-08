# GitHub Actions セットアップガイド

## 概要

このプロジェクトでは以下のGitHub Actionsワークフローが定期実行されます：

1. **論文サマライズ** (`summarize.yml`) - 毎日朝9時
2. **フィードバック分析・自動フィルター更新** (`feedback-analyzer.yml`) - 毎週日曜朝9時

## 必要なSecrets設定

GitHub リポジトリの Settings → Secrets and variables → Actions で以下のSecretsを設定してください。

### 基本的なSecrets

| Secret名 | 説明 | 取得方法 |
|----------|------|----------|
| `GEMINI_API_KEY` | Google Gemini APIキー | [Google AI Studio](https://makersuite.google.com/app/apikey) |
| `SLACK_WEBHOOK_URL` | Slack通知用WebhookURL | [Slack App設定手順](#slack-webhook設定) |
| `GH_PAT` | GitHub Personal Access Token | [GitHub PAT設定手順](#github-pat設定) |

### 各Secretの詳細設定手順

#### 1. GEMINI_API_KEY

1. [Google AI Studio](https://makersuite.google.com/app/apikey)にアクセス
2. 「Get API key」をクリック
3. 生成されたAPIキーをコピー
4. GitHub Secretsに `GEMINI_API_KEY` として設定

#### 2. SLACK_WEBHOOK_URL

1. [Slack API](https://api.slack.com/apps)にアクセス
2. 「Create New App」→「From scratch」を選択
3. App名（例：RSS論文サマライザー）とワークスペースを選択
4. 左メニューから「Incoming Webhooks」を選択
5. 「Activate Incoming Webhooks」をONにする
6. 「Add New Webhook to Workspace」をクリック
7. 投稿先のチャンネルを選択
8. 生成されたWebhook URL（`https://hooks.slack.com/services/...`）をコピー
9. GitHub Secretsに `SLACK_WEBHOOK_URL` として設定

#### 3. GH_PAT (GitHub Personal Access Token)

1. GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. 「Generate new token」→「Generate new token (classic)」を選択
3. Note: 「RSS AI Reporter Actions」など分かりやすい名前を入力
4. Expiration: 適切な期限を設定（推奨：1年）
5. 以下のスコープを選択：
   - `repo` (Full control of private repositories)
   - `workflow` (Update GitHub Action workflows)
   - `write:packages` (Upload packages to GitHub Package Registry)
6. 「Generate token」をクリック
7. 生成されたトークンをコピー（一度しか表示されません）
8. GitHub Secretsに `GH_PAT` として設定

## ワークフロー設定

### 1. 論文サマライズ (summarize.yml)

- **実行頻度**: 毎日朝9時（JST）
- **主な機能**: RSS取得、論文サマライズ、Slack通知
- **手動実行**: 可能
- **必要なSecrets**: `GEMINI_API_KEY`, `SLACK_WEBHOOK_URL`

### 2. フィードバック分析 (feedback-analyzer.yml)

- **実行頻度**: 毎週日曜朝9時（JST）
- **主な機能**: フィードバック分析、自動フィルター更新、PR作成
- **手動実行**: 可能（パラメータ指定可能）
- **必要なSecrets**: `GEMINI_API_KEY`, `SLACK_WEBHOOK_URL`, `GH_PAT`

#### 手動実行時のパラメータ

| パラメータ | デフォルト値 | 説明 |
|------------|--------------|------|
| `analysis_days` | 30 | フィードバック分析対象期間（日数） |
| `min_feedback` | 10 | 自動更新に必要な最小フィードバック数 |
| `min_confidence` | 7 | 自動更新に必要な最小信頼度スコア |
| `dry_run` | false | Dry-runモード（実際の変更なし） |
| `analysis_only` | false | 分析のみ実行（自動更新スキップ） |

## トラブルシューティング

### よくある問題と解決策

#### 1. "Gemini API key is required" エラー

**原因**: `GEMINI_API_KEY` が設定されていない、または無効
**解決策**: 
- Secretsに正しいAPIキーが設定されているか確認
- APIキーが有効で、制限に達していないか確認

#### 2. "GitHub CLI not authenticated" エラー

**原因**: `GH_PAT` が設定されていない、または権限不足
**解決策**:
- `GH_PAT` Secretが正しく設定されているか確認
- トークンに `repo` と `workflow` スコープが含まれているか確認
- トークンの有効期限が切れていないか確認

#### 3. Slack通知が届かない

**原因**: `SLACK_WEBHOOK_URL` が無効、またはSlack App設定の問題
**解決策**:
- Webhook URLが正しく設定されているか確認
- Slack App の Incoming Webhooks が有効になっているか確認
- チャンネルへの投稿権限があるか確認

#### 4. "Insufficient feedback data" で自動更新がスキップされる

**原因**: フィードバックデータが不足している
**解決策**:
- 手動実行時に `min_feedback` パラメータを下げる
- より多くのフィードバックが蓄積されるまで待つ
- `analysis_only: true` で分析のみ実行して状況を確認

### ログの確認方法

1. GitHub リポジトリ → Actions タブ
2. 該当するワークフロー実行をクリック
3. 各ステップのログを確認

### 緊急時の対応

#### ワークフローを一時停止したい場合

1. `.github/workflows/feedback-analyzer.yml` の `schedule` セクションをコメントアウト
2. プルリクエストを作成してマージ

#### 手動で緊急分析を実行したい場合

1. Actions タブ → 「フィードバック分析・自動フィルター更新」
2. 「Run workflow」をクリック
3. 適切なパラメータを設定して実行

## セキュリティ考慮事項

- **Secrets管理**: 
  - APIキーやトークンは定期的にローテーションする
  - 不要になったトークンは即座に削除する
  
- **権限最小化**:
  - GitHub PATは必要最小限のスコープのみ付与
  - Slack Appは必要なチャンネルのみにアクセス許可

- **監査ログ**:
  - GitHub Actions の実行ログは定期的に確認
  - 異常な実行パターンがないかモニタリング

## 更新履歴

- 2025-06-08: 初版作成
- 2025-06-08: Phase 6-5 定期実行システム対応