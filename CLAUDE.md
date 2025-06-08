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

## メモリ情報

- python libraryはuv venvを使って導入、activeteすること

---

## 🚧 改善計画 (2025年6月)

### 現在の問題
1. **要約が空で表示される**: `summary_ja`フィールドが生成されていない
2. **記事タイプの混在**: 論文(`s41586`)とニュース記事(`d41586`)が混在、ノイズが多い
3. **Abstract取得の失敗**: BeautifulSoupセレクタが古い可能性
4. **デバッグ情報不足**: 問題箇所の特定が困難

### 改善計画の段階

#### Phase 1: 🔍 デバッグと可視化強化 ✅ **完了 (PR#3)**
- [x] 新ブランチ作成: `feature/debug-improvements`
- [x] 詳細ログ追加 (各段階でのデータ出力)
- [x] デバッグモード追加 (`--debug`フラグ)
- [x] 個別URL テスト機能 (`--test-url`)
- [x] Gemini API呼び出し結果の詳細ログ

#### Phase 2: 🛠️ コンテンツ取得の改善 ✅ **完了 (PR#4)**
- [x] 記事タイプフィルタリング (論文記事優先)
- [x] BeautifulSoupセレクタの最新化 (2025年対応)
- [x] フォールバック機能強化 (RSS summary → メタタグ → 一般セレクタ)
- [x] エラーハンドリング強化 (部分的情報での処理継続)

#### Phase 3: 🤖 サマライズ機能の修正 ✅ **完了 (PR#5)**
- [x] `summary_ja`フィールド生成の確実化
- [x] Gemini API処理の確認とエラーハンドリング
- [x] 代替要約ソース (RSSのsummary活用、タイトルベース簡易要約)
- [x] 文字数制限強化 (200-250文字)

#### Phase 4: 🎯 フィルタリング強化 ✅ **完了 (PR#4)**
- [x] 記事タイプベースフィルタ (Research articles優先)
- [x] 品質フィルタ (Abstract有無、著者数・機関情報)
- [x] News/Opinion/Editorial除外オプション
- [x] スマートURLパターン分析

#### Phase 5: 🧪 テスト環境整備 ✅ **完了**
- [x] `--slack-test` テスト用Slack通知
- [x] `--slack-test-real` 実際のGemini要約でテスト
- [x] `--summarize-test` サマライズ機能単体テスト
- [x] デバッグログとエラーハンドリング強化

---

## 🤖 継続学習システム実装計画 (Phase 6)

### システム概要
ユーザーフィードバックを自動収集し、AIでパターン分析してフィルター設定を進化させる仕組み。

### 実装段階

#### Phase 6-1: 📱 Slackフィードバック機能 ✅ **完了 (PR#6)**
- [x] `slack_notifier.py`にフィードバックボタン追加
- [x] 各論文に👍👎ボタンを配置
- [x] ボタンクリック時のペイロード設計（記事ID + フィードバック）
- [x] Slack App設定（Interactive Components有効化）
- [x] **3エントリ限定モードの実装** (`--slack-test-3`)

#### Phase 6-2: 🔗 フィードバック収集システム ✅ **完了 (PR#7)**
- [x] `feedback_handler.py`新規作成
- [x] GitHub Issues APIでフィードバック記録
- [x] フィードバック受信用Webhookエンドポイント (Flask開発用)
- [x] データ構造設計（記事ID、フィードバック、タイムスタンプ、ユーザー）
- [x] **AWS Lambda サーバーレス実装** (本番デプロイ済み)
- [x] **API Gateway HTTPS エンドポイント** (https://ryys05qyq7.execute-api.us-east-1.amazonaws.com/prod)
- [x] **S3 フィードバックログ保存**
- [x] **SAM テンプレートによる Infrastructure as Code**

#### Phase 6-3: 🧠 AI分析エンジン ✅ **完了 (PR#12)**
- [x] `feedback_analyzer.py`新規作成
- [x] Gemini APIでフィードバックパターン分析
- [x] 興味ありパターンの特徴抽出（キーワード、著者、ジャーナル）
- [x] 興味なしパターンの特徴抽出
- [x] 新キーワード候補の提案ロジック

#### Phase 6-4: 🔄 自動フィルター更新 ✅ **完了 (PR#13)**
- [x] `auto_updater.py`新規作成
- [x] 分析結果から`filter_config.json`更新提案
- [x] 自動ブランチ作成・コミット・プッシュ
- [x] GitHub CLI使用した自動PR作成
- [x] 人間レビュー後のマージワークフロー

#### Phase 6-5: ⏰ 定期実行システム ✅ **完了 (PR#14)**
- [x] `.github/workflows/feedback-analyzer.yml`作成
- [x] 週次でフィードバック分析実行
- [x] 閾値超過時の自動PR作成（最低10件のフィードバック）
- [x] エラー通知とフォールバック

### 必要な設定
- **Slack App**: ✅ Interactive Components有効化済み
- **GitHub**: ✅ Personal Access Token設定済み  
- **GitHub Secrets**: ✅ `GITHUB_TOKEN`追加済み
- **AWS Lambda**: ✅ 本番環境デプロイ済み

### データフロー
```
Slack通知(3件) → フィードバックボタン → AWS Lambda → 
S3 + GitHub Issue → 週次分析 → フィルター提案 → 
自動PR → 人間レビュー → マージ
```

### タイムライン（単位実装）

**Week 1: Phase 6-1** - ✅ 完了 `feature/slack-feedback-buttons`
**Week 2: Phase 6-2** - ✅ 完了 `feature/feedback-collection`
**Week 3: Phase 6-3** - ✅ 完了 `feature/ai-feedback-analysis`  
**Week 4: Phase 6-4** - ✅ 完了 `feature/auto-filter-updates`
**Week 5: Phase 6-5** - ✅ 完了 `feature/scheduled-analysis`

### テスト・検証方法
- **3エントリテスト**: `python src/main.py --slack-test-3`で動作確認
- 個別URL でのコンテンツ取得テスト (`--test-url`)
- Gemini API レスポンス確認 (`--summarize-test`)
- 段階的なデバッグログでボトルネック特定 (`--debug`)

## 📊 現在のシステム状態

### ✅ 実装完了
- **基本機能**: RSS取得、論文サマライズ、Slack通知
- **改善機能**: デバッグモード、コンテンツ取得改善、フィルタリング強化
- **継続学習システム**: フィードバック収集、AI分析、自動フィルター更新、定期実行

### 🚀 本番運用中
- **AWS Lambda Webhook**: https://ryys05qyq7.execute-api.us-east-1.amazonaws.com/prod/slack/feedback
- **毎日の論文通知**: GitHub Actions (毎朝9時JST)
- **週次フィードバック分析**: GitHub Actions (毎週日曜9時JST)
- **自動フィルター更新**: 閾値超過時の自動PR作成

---

## 🚀 システム拡張計画 (Phase 7)

### Phase A: データ管理の改善（短期 - 1-2週間）

#### A1. チェックポイント最適化
- [ ] **古いエントリ自動削除**: 30-90日経過した`seen_articles`エントリを削除
- [ ] **ファイルサイズ管理**: 定期的なクリーンアップで性能維持  
- [ ] **統計データ保持**: 削除前に月次統計を生成・保存

#### A2. キュー管理強化
- [ ] **処理失敗リトライ**: エラー時の自動再試行機能
- [ ] **優先度付きキュー**: 重要論文の優先処理システム
- [ ] **バッチサイズ調整**: 処理能力に応じた動的調整

#### A3. データアーカイブ機能  
- [ ] **月次アーカイブ**: 古いデータを別ファイルに移動
- [ ] **圧縮保存**: gzip圧縮でストレージ効率化

### Phase B: RSS拡張性の向上（中期 - 2-4週間）

#### B1. 設定ファイル化
- [ ] **RSS設定外部化**: `data/rss_config.json`を新規作成
- [ ] **動的サイト管理**: 有効/無効切り替え、優先度設定
- [ ] **設定構造設計**:
  ```json
  {
    "rss_sources": {
      "nature": {
        "name": "Nature",
        "rss_url": "https://www.nature.com/nature.rss",
        "parser_type": "nature", 
        "enabled": true,
        "priority": 1
      },
      "science": {
        "name": "Science",
        "rss_url": "https://www.science.org/rss/news_current.xml",
        "parser_type": "science",
        "enabled": true, 
        "priority": 1
      }
    }
  }
  ```

#### B2. プラガブルパーサーシステム
- [ ] **抽象基底クラス**: `src/parsers/base_parser.py`作成
- [ ] **既存パーサー移行**: `src/parsers/nature_parser.py`, `science_parser.py`
- [ ] **動的ロード機能**: 設定に基づく適切なパーサー選択
- [ ] **フォールバック処理**: 汎用パーサーによる基本的な処理

#### B3. 新サイト追加の簡素化
- [ ] **設定ファイル追加のみ**: コード変更なしでの新サイト対応
- [ ] **パーサーテンプレート**: 新パーサー作成用ボイラープレート
- [ ] **自動検出機能**: RSS構造からの適切なパーサー推定

#### B4. 候補追加サイト
- [ ] **Cell**: 生物学分野のトップジャーナル
- [ ] **NEJM**: 医学分野の最高峰 
- [ ] **PNAS**: 米国科学アカデミー紀要
- [ ] **arXiv**: AI/物理/数学のプレプリント
- [ ] **PLoS ONE**: オープンアクセス総合誌

#### B5. テスト基盤整備
- [ ] **RSS パーサーテスト**: `test/test_rss_parsers.py`
  - 各サイトのRSSサンプルデータ
  - パース成功率測定
  - エラーハンドリング検証

- [ ] **コンテンツ取得テスト**: `test/test_content_fetchers.py`  
  - 実際のサンプルURL群でのテスト
  - アブストラクト取得成功率測定
  - 著者情報抽出精度検証

- [ ] **Gemini統合テスト**: `test/test_gemini_integration.py`
  - サイト別要約品質テスト
  - エラー率測定
  - 文字数・形式チェック

- [ ] **エンドツーエンドテスト**: `test/test_e2e_new_sites.py`
  - 新サイト追加から通知までの全工程
  - パフォーマンス測定
  - データ品質検証

- [ ] **テストデータ管理**: `test/data/`
  - 各サイトの代表的なRSSサンプル
  - 典型的な論文ページのHTMLサンプル
  - 期待される出力データ

### 実装優先度
1. **Phase A1-A2**: データ管理の基盤強化（現在の課題解決）
2. **Phase B1-B2**: 拡張性基盤の構築（設定外部化、パーサー抽象化）
3. **Phase B5**: テスト基盤整備（品質保証の確立）
4. **Phase A3, B3-B4**: 高度機能とサイト追加（段階的拡張）

### 期待される効果
- **スケーラビリティ**: 2サイト → 数十サイトへの拡張対応
- **保守性**: 新サイト追加の工数大幅削減（設定ファイル追加のみ）
- **品質保証**: 新サイト追加時の自動テストによる品質担保
- **信頼性**: エラー復旧、データ整合性の向上
- **Gemini互換性**: コンテンツ品質とAI処理成功率の保証