#!/usr/bin/env python3
import sys
import json
import os
import argparse
from typing import List, Dict, Any
from datetime import datetime

# 環境変数を .env ファイルから読み込み
try:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from scripts.load_env import load_env
    load_env()
except ImportError:
    pass  # スクリプトがない場合はスキップ

from rss_fetcher import RSSFetcher
from content_fetcher import ContentFetcher
from summarizer import Summarizer
from slack_notifier import SlackNotifier
from feedback_analyzer import FeedbackAnalyzer
from auto_updater import AutoFilterUpdater
from queue_manager import QueueManager
from archive_manager import ArchiveManager

class PaperSummarizerPipeline:
    def __init__(self, debug_mode: bool = False):
        self.debug_mode = debug_mode
        self.rss_fetcher = RSSFetcher()
        self.content_fetcher = ContentFetcher(debug_mode=debug_mode)
        self.summarizer = Summarizer(debug_mode=debug_mode)
        self.slack_notifier = SlackNotifier(enable_feedback=True)
        self.queue_manager = QueueManager()
        self.archive_manager = ArchiveManager()
        self.filter_config_file = "data/filter_config.json"
        
    def debug_print(self, message: str, data: Any = None):
        """デバッグモード時のみ詳細情報を出力"""
        if self.debug_mode:
            print(f"[DEBUG] {message}")
            if data is not None:
                if isinstance(data, (dict, list)):
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                else:
                    print(data)
            print("-" * 50)
        
    def show_queue_stats(self):
        """キューの統計情報を表示"""
        queue_info = self.queue_manager.get_queue_info()
        print(f"📊 Queue Status: {queue_info['total_items']} articles")
        
        if queue_info['total_items'] > 0:
            priority_stats = queue_info['priority_breakdown']
            for priority, count in priority_stats.items():
                if count > 0:
                    print(f"   {priority}: {count} articles")
            
            if queue_info['oldest_item']:
                print(f"   Oldest: {queue_info['oldest_item'][:19]}")
            if queue_info['newest_item']:
                print(f"   Newest: {queue_info['newest_item'][:19]}")
        
        # 古いアイテムのクリーンアップ
        removed = self.queue_manager.cleanup_old_items()
        if removed > 0:
            print(f"🧹 Cleaned up {removed} old items")
    
    def load_filter_config(self) -> Dict[str, List[str]]:
        if os.path.exists(self.filter_config_file):
            with open(self.filter_config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"include": [], "exclude": [], "research_only": True}
    
    def filter_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        filter_config = self.load_filter_config()
        include_keywords = [kw.lower() for kw in filter_config.get("include", [])]
        exclude_keywords = [kw.lower() for kw in filter_config.get("exclude", [])]
        research_only = filter_config.get("research_only", True)  # デフォルトで論文のみ
        
        filtered_articles = []
        filtered_stats = {
            "total": len(articles),
            "research_filter": 0,
            "keyword_filter": 0,
            "passed": 0
        }
        
        for article in articles:
            # 論文フィルター
            if research_only:
                # URLパターンで簡易判定
                url = article.get('link', '')
                if 'd41586' in url:  # Nature news
                    self.debug_print(f"Filtered out (News): {article.get('title', '')[:50]}...")
                    filtered_stats["research_filter"] += 1
                    continue
            
            # 検索対象のテキストを結合
            search_text = " ".join([
                article.get('title', ''),
                article.get('abstract', ''),
                article.get('summary', ''),
                " ".join(article.get('keywords', []))
            ]).lower()
            
            # 除外キーワードチェック
            if any(keyword in search_text for keyword in exclude_keywords):
                self.debug_print(f"Filtered out (Exclude keyword): {article.get('title', '')[:50]}...")
                filtered_stats["keyword_filter"] += 1
                continue
            
            # 含むキーワードチェック（指定がある場合）
            if include_keywords:
                if not any(keyword in search_text for keyword in include_keywords):
                    self.debug_print(f"Filtered out (Include keyword): {article.get('title', '')[:50]}...")
                    filtered_stats["keyword_filter"] += 1
                    continue
            
            filtered_articles.append(article)
            filtered_stats["passed"] += 1
        
        self.debug_print("Filtering statistics:", filtered_stats)
        return filtered_articles
    
    def test_single_url(self, url: str):
        """単一URLのコンテンツ取得とサマライズをテスト"""
        print(f"Testing single URL: {url}")
        
        # 記事の基本情報を作成
        if "nature.com" in url:
            journal = "Nature"
        elif "science.org" in url:
            journal = "Science"
        else:
            journal = "Unknown"
            
        article = {
            "id": url,
            "journal": journal,
            "title": "Test Article",
            "link": url,
            "published": "",
            "summary": "",
            "authors": [],
            "doi": ""
        }
        
        self.debug_print("Initial article data:", article)
        
        # コンテンツ取得
        print("\n1. Fetching content details...")
        updated_article = self.content_fetcher.fetch_article_details(article)
        self.debug_print("After content fetching:", updated_article)
        
        # サマライズ
        print("\n2. Summarizing article...")
        try:
            summarized_articles = self.summarizer.batch_summarize([updated_article])
            if summarized_articles:
                self.debug_print("After summarization:", summarized_articles[0])
                print(f"\n3. Summary result:")
                print(f"Title: {summarized_articles[0].get('title', 'N/A')}")
                print(f"Authors: {', '.join(summarized_articles[0].get('authors', []))}")
                print(f"Abstract: {summarized_articles[0].get('abstract', 'N/A')[:200]}...")
                print(f"Japanese Summary: {summarized_articles[0].get('summary_ja', 'N/A')}")
            else:
                print("No summary generated")
        except Exception as e:
            print(f"Error during summarization: {e}")
            
    def run_slack_test(self, use_real_summaries: bool = False):
        """キューからの記事でSlack通知をテストする"""
        try:
            queue = self.queue_manager.load_queue()
            if not queue:
                print("No articles in queue for testing")
                return
                
            # キューから最大3件取得（テスト用）
            articles_to_notify = queue[:3]
            print(f"Testing Slack notification with {len(articles_to_notify)} articles...")
            
            if use_real_summaries:
                print("Generating real summaries with Gemini API...")
                # 実際にGemini APIで要約生成
                summarized_articles = self.summarizer.batch_summarize(articles_to_notify)
                articles_to_notify = summarized_articles
            else:
                # summary_jaフィールドが存在しない場合は追加
                for i, article in enumerate(articles_to_notify):
                    if 'summary_ja' not in article or not article['summary_ja']:
                        print(f"Article {i+1} missing summary_ja, generating fallback...")
                        article['summary_ja'] = self.summarizer._generate_fallback_summary(
                            article.get('title', ''),
                            article.get('abstract', article.get('summary', '')),
                            article.get('authors', []),
                            article.get('journal', '')
                        )
            
            self.debug_print("Articles to notify:", [
                {k: v for k, v in article.items() if k in ['title', 'summary_ja', 'authors']}
                for article in articles_to_notify
            ])
            
            success = self.slack_notifier.send_notification(articles_to_notify)
            if success:
                print("Slack notification sent successfully!")
            else:
                print("Failed to send Slack notification")
                
        except Exception as e:
            print(f"Error during Slack test: {e}")
    
    def run_summarization_test(self):
        """キューからの記事でサマライズ機能をテストする"""
        try:
            queue = self.queue_manager.load_queue()
            if not queue:
                print("No articles in queue for testing")
                return
                
            # キューから最大2件取得（テスト用）
            articles_to_test = queue[:2]
            print(f"Testing summarization with {len(articles_to_test)} articles...")
            
            for i, article in enumerate(articles_to_test):
                print(f"\n--- Testing Article {i+1} ---")
                print(f"Title: {article.get('title', 'N/A')}")
                print(f"Has abstract: {bool(article.get('abstract'))}")
                print(f"Has summary: {bool(article.get('summary'))}")
                print(f"Authors count: {len(article.get('authors', []))}")
                
                # サマライズ実行
                result = self.summarizer.batch_summarize([article])
                if result:
                    print(f"Summary generated: {len(result[0].get('summary_ja', ''))} characters")
                    print(f"Preview: {result[0].get('summary_ja', 'N/A')[:100]}...")
                else:
                    print("No summary generated")
                
        except Exception as e:
            print(f"Error during summarization test: {e}")

    def run_slack_test_3(self, use_real_summaries: bool = False):
        """3エントリ限定でフィードバックボタン付きSlack通知をテストする"""
        try:
            queue = self.queue_manager.load_queue()
            if not queue:
                print("No articles in queue for testing")
                return
                
            # キューから3件限定で取得
            articles_to_notify = queue[:3]
            print(f"Testing Slack notification with feedback buttons for {len(articles_to_notify)} articles...")
            
            if use_real_summaries:
                print("Generating real summaries with Gemini API...")
                # 実際にGemini APIで要約生成
                summarized_articles = self.summarizer.batch_summarize(articles_to_notify)
                articles_to_notify = summarized_articles
            else:
                # summary_jaフィールドが存在しない場合は追加
                for i, article in enumerate(articles_to_notify):
                    if 'summary_ja' not in article or not article['summary_ja']:
                        print(f"Article {i+1} missing summary_ja, generating fallback...")
                        article['summary_ja'] = self.summarizer._generate_fallback_summary(
                            article.get('title', ''),
                            article.get('abstract', article.get('summary', '')),
                            article.get('authors', []),
                            article.get('journal', '')
                        )
            
            self.debug_print("Articles to notify (with feedback):", [
                {k: v for k, v in article.items() if k in ['title', 'summary_ja', 'authors']}
                for article in articles_to_notify
            ])
            
            # フィードバック機能を有効にしたSlackNotifierを作成
            feedback_notifier = SlackNotifier(enable_feedback=True)
            success = feedback_notifier.send_notification(articles_to_notify)
            
            if success:
                print("✅ Slack notification with feedback buttons sent successfully!")
                print("📝 Note: To handle feedback responses, you need to:")
                print("   1. Set up Interactive Components in your Slack App")
                print("   2. Configure a Request URL for button clicks")
                print("   3. Implement feedback handler (Phase 6-2)")
            else:
                print("❌ Failed to send Slack notification")
                
        except Exception as e:
            print(f"Error during Slack test with feedback: {e}")

    def run_feedback_analysis(self, days: int = 30, min_feedback: int = 3, close_issues: bool = True):
        """フィードバック分析を実行"""
        try:
            print("🧠 Starting feedback analysis...")
            print(f"📊 Analyzing feedback from last {days} days (minimum {min_feedback} entries)")
            
            # FeedbackAnalyzerを初期化
            analyzer = FeedbackAnalyzer(debug=self.debug_mode)
            
            # 分析実行
            result = analyzer.run_analysis(days=days, min_feedback=min_feedback, close_issues=close_issues)
            
            # 結果表示
            print("\n" + "="*60)
            print("📊 FEEDBACK ANALYSIS RESULTS")
            print("="*60)
            
            if result['status'] == 'insufficient_data':
                print(f"❌ {result['message']}")
                print(f"   Current feedback count: {result['data_count']}")
                print(f"   Required minimum: {min_feedback}")
                return
            
            print(f"✅ Analysis completed successfully!")
            print(f"📈 Data analyzed: {result['data_count']} feedback entries")
            print(f"⏱️  Period: {result['analysis_period']}")
            
            # 統計情報
            stats = result['patterns']['statistics']
            print(f"\n📊 Feedback Statistics:")
            print(f"   👍 Interested: {stats['interested_count']}")
            print(f"   👎 Not interested: {stats['not_interested_count']}")
            print(f"   📊 Interest rate: {stats['interested_count']/(stats['total_feedback'])*100:.1f}%")
            
            # AI分析結果
            ai_analysis = result['ai_analysis']
            print(f"\n🤖 AI Analysis Summary:")
            print(f"   {ai_analysis.get('summary', 'No summary available')}")
            
            # フィルター推奨事項
            recommendations = result['filter_recommendations']
            print(f"\n🎯 Filter Recommendations:")
            
            suggested_includes = recommendations['suggested_additions']['include']
            suggested_excludes = recommendations['suggested_additions']['exclude']
            
            if suggested_includes:
                print(f"   ➕ Suggested INCLUDE keywords: {', '.join(suggested_includes)}")
            if suggested_excludes:
                print(f"   ➖ Suggested EXCLUDE keywords: {', '.join(suggested_excludes)}")
            
            if not suggested_includes and not suggested_excludes:
                print("   ℹ️  No new keyword suggestions (current filters may be optimal)")
            
            print(f"\n💡 Reasoning: {recommendations.get('reasoning', 'No reasoning provided')}")
            print(f"🎯 Confidence Score: {recommendations.get('confidence', 0)}/10")
            
            # Issue クローズ情報
            if 'closed_issues' in result:
                print(f"\n📋 Issue Management:")
                print(f"   ✅ Closed {result['closed_issues']} feedback issues")
            
            # デバッグモードの場合は詳細情報も表示
            if self.debug_mode:
                print(f"\n🔍 Full Analysis Result:")
                print(json.dumps(result, indent=2, ensure_ascii=False))
            
            print("\n" + "="*60)
            print("💡 Next Steps:")
            print("   1. Review the suggested keywords above")
            print("   2. Update data/filter_config.json manually, or")
            print("   3. Wait for Phase 6-4 auto-update feature")
            print("="*60)
            
        except Exception as e:
            print(f"❌ Error during feedback analysis: {e}")
            if self.debug_mode:
                import traceback
                traceback.print_exc()

    def run_auto_filter_update(self, 
                              days: int = 30, 
                              min_feedback: int = 5,
                              min_confidence: int = 6,
                              dry_run: bool = False):
        """自動フィルター更新を実行"""
        try:
            print("🔄 Starting automatic filter update...")
            print(f"📊 Parameters: {days} days, min {min_feedback} feedback, confidence ≥{min_confidence}")
            
            if dry_run:
                print("🧪 Running in DRY RUN mode (no actual changes will be made)")
            
            # AutoFilterUpdaterを初期化
            updater = AutoFilterUpdater(debug=self.debug_mode, dry_run=dry_run)
            
            # 自動更新実行
            result = updater.run_auto_update(
                days=days,
                min_feedback=min_feedback,
                min_confidence=min_confidence
            )
            
            # 結果表示
            print("\n" + "="*60)
            print("🔄 AUTO FILTER UPDATE RESULTS")
            print("="*60)
            
            status = result['status']
            message = result['message']
            
            if status == 'success':
                print(f"✅ Update completed successfully!")
                print(f"🌟 {message}")
                
                update_info = result['update_info']
                changes = update_info['changes']
                
                print(f"\n📈 Update Summary:")
                print(f"   🎯 Confidence Score: {update_info['confidence']}/10")
                print(f"   📊 Based on: {update_info['data_count']} feedback entries")
                
                if changes['added_includes']:
                    print(f"   ➕ Added INCLUDE keywords: {', '.join(changes['added_includes'])}")
                if changes['added_excludes']:
                    print(f"   ➖ Added EXCLUDE keywords: {', '.join(changes['added_excludes'])}")
                
                print(f"\n🔗 Pull Request: {result['pr_url']}")
                print(f"🌿 Branch: {result['branch_name']}")
                
            elif status == 'skipped':
                print(f"⏭️  Update skipped: {message}")
                
                # スキップ理由に応じて詳細説明
                if 'confidence' in message.lower():
                    print(f"   💡 Tip: Lower --min-confidence to allow updates with lower confidence")
                elif 'feedback' in message.lower():
                    print(f"   💡 Tip: Wait for more user feedback or lower --min-feedback")
                elif 'keyword' in message.lower():
                    print(f"   💡 Info: Current filters may already be optimal")
                
            else:  # error
                print(f"❌ Update failed: {message}")
                stage = result.get('stage', 'unknown')
                print(f"   Failed at stage: {stage}")
                
                # ステージ別のトラブルシューティング
                if stage == 'prerequisites':
                    print(f"   💡 Check: gh auth login, git status, file permissions")
                elif stage == 'analysis':
                    print(f"   💡 Check: feedback data availability, API keys")
                elif stage in ['git', 'pr']:
                    print(f"   💡 Check: GitHub authentication, repository permissions")
            
            # デバッグモードの場合は詳細情報も表示
            if self.debug_mode:
                print(f"\n🔍 Full Result:")
                print(json.dumps(result, indent=2, ensure_ascii=False))
            
            print("\n" + "="*60)
            if status == 'success':
                print("💡 Next Steps:")
                print("   1. Review the created pull request")
                print("   2. Test the proposed filter changes")
                print("   3. Merge the PR to apply changes")
            elif status == 'skipped':
                print("💡 Try Again:")
                print("   - Use --dry-run to test without making changes")
                print("   - Adjust parameters (--min-confidence, --min-feedback)")
                print("   - Wait for more user feedback data")
            else:
                print("💡 Troubleshooting:")
                print("   - Check prerequisites with --debug")
                print("   - Use --dry-run to test safely")
                print("   - Review logs for specific error details")
            print("="*60)
            
        except Exception as e:
            print(f"❌ Error during auto filter update: {e}")
            if self.debug_mode:
                import traceback
                traceback.print_exc()

    def run(self, test_mode: bool = False):
        try:
            print("Starting RSS Paper Summarizer...")
            
            # 1. RSS取得
            print("\n1. Fetching RSS feeds...")
            new_articles = self.rss_fetcher.fetch_new_articles()
            print(f"Found {len(new_articles)} new articles")
            self.debug_print("New articles sample:", new_articles[:2] if new_articles else [])
            
            # 2. キューから未処理記事を取得（新システム）
            self.queue_manager.add_articles(new_articles)
            
            # キュー統計表示
            self.show_queue_stats()
            
            # 処理対象記事を取得
            articles_to_process = self.queue_manager.get_batch(batch_size=20)
            total_articles = articles_to_process
            
            if not total_articles:
                print("No articles to process")
                return
            
            # 3. フィルタリング
            print("\n2. Filtering articles...")
            filtered_articles = self.filter_articles(total_articles)
            print(f"After filtering: {len(filtered_articles)} articles")
            self.debug_print("Filtered articles sample:", filtered_articles[:2] if filtered_articles else [])
            
            if not filtered_articles:
                print("No articles passed the filter")
                return
            
            # 4. 記事を処理用に設定
            articles_to_process = filtered_articles
            
            # 5. 論文詳細取得
            print(f"\n3. Fetching article details for {len(articles_to_process)} articles...")
            for i, article in enumerate(articles_to_process):
                print(f"Fetching details {i+1}/{len(articles_to_process)}: {article.get('title', '')[:50]}...")
                self.debug_print(f"Before content fetching #{i+1}:", article)
                self.content_fetcher.fetch_article_details(article)
                self.debug_print(f"After content fetching #{i+1}:", article)
            
            # 6. サマライズ
            print("\n4. Summarizing articles...")
            self.debug_print("Articles before summarization:", [a.get('title') for a in articles_to_process])
            summarized_articles = self.summarizer.batch_summarize(articles_to_process)
            
            # サマライズ後の検証とフォールバック
            for article in summarized_articles:
                if not article.get('summary_ja'):
                    print(f"  WARNING: Missing summary_ja for '{article.get('title', '')[:50]}', adding fallback...")
                    article['summary_ja'] = self.summarizer._generate_fallback_summary(
                        article.get('title', ''),
                        article.get('abstract', article.get('summary', '')),
                        article.get('authors', []),
                        article.get('journal', '')
                    )
            
            self.debug_print("Articles after summarization:", [{k: v for k, v in a.items() if k in ['title', 'summary_ja']} for a in summarized_articles[:2]])
            
            # 7. Slack通知
            if not test_mode:
                print("\n5. Sending Slack notification...")
                success = self.slack_notifier.send_notification(summarized_articles)
                if not success:
                    print("Failed to send Slack notification")
            else:
                print("\n5. Test mode - Skipping Slack notification")
                print("Sample output:")
                for article in summarized_articles[:2]:
                    print(f"\nTitle: {article.get('title', '')}")
                    print(f"Summary: {article.get('summary_ja', '')[:100]}...")
            
            # 8. 処理済み記事をアーカイブ
            if not test_mode:
                archived_count = self.archive_manager.archive_processed_articles(summarized_articles)
                print(f"\n📦 Archived {archived_count} processed articles")
            
            print("\nPipeline completed successfully!")
            
        except Exception as e:
            error_msg = f"Pipeline error: {str(e)}"
            print(f"\nERROR: {error_msg}")
            
            # エラー通知
            if not test_mode:
                self.slack_notifier.send_error_notification(error_msg)
            
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='RSS Paper Summarizer')
    parser.add_argument('--test', action='store_true', help='Run in test mode (no Slack notification)')
    parser.add_argument('--slack-test', action='store_true', help='Test Slack notification with queued articles')
    parser.add_argument('--slack-test-real', action='store_true', help='Test Slack notification with real Gemini summaries')
    parser.add_argument('--slack-test-3', action='store_true', help='Test Slack notification with feedback buttons (3 articles)')
    parser.add_argument('--slack-test-3-real', action='store_true', help='Test Slack notification with feedback buttons and real summaries')
    parser.add_argument('--summarize-test', action='store_true', help='Test summarization with queued articles')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode with detailed logging')
    parser.add_argument('--test-url', type=str, help='Test content fetching and summarization for a single URL')
    parser.add_argument('--analyze-feedback', action='store_true', help='Run feedback analysis and generate filter recommendations')
    parser.add_argument('--feedback-days', type=int, default=30, help='Days of feedback data to analyze (default: 30)')
    parser.add_argument('--feedback-min', type=int, default=3, help='Minimum feedback count for analysis (default: 3)')
    parser.add_argument('--no-close-issues', action='store_true', help='Skip closing GitHub issues after analysis')
    parser.add_argument('--auto-update', action='store_true', help='Run automatic filter update based on feedback analysis')
    parser.add_argument('--auto-min-feedback', type=int, default=5, help='Minimum feedback count for auto-update (default: 5)')
    parser.add_argument('--auto-min-confidence', type=int, default=6, help='Minimum confidence score for auto-update (default: 6)')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode for auto-update (no actual changes)')
    args = parser.parse_args()
    
    pipeline = PaperSummarizerPipeline(debug_mode=args.debug)
    
    if args.test_url:
        pipeline.test_single_url(args.test_url)
    elif args.auto_update:
        pipeline.run_auto_filter_update(
            days=args.feedback_days, 
            min_feedback=args.auto_min_feedback,
            min_confidence=args.auto_min_confidence,
            dry_run=args.dry_run
        )
    elif args.analyze_feedback:
        pipeline.run_feedback_analysis(days=args.feedback_days, min_feedback=args.feedback_min, close_issues=not args.no_close_issues)
    elif args.slack_test:
        pipeline.run_slack_test(use_real_summaries=False)
    elif args.slack_test_real:
        pipeline.run_slack_test(use_real_summaries=True)
    elif args.slack_test_3:
        pipeline.run_slack_test_3(use_real_summaries=False)
    elif args.slack_test_3_real:
        pipeline.run_slack_test_3(use_real_summaries=True)
    elif args.summarize_test:
        pipeline.run_summarization_test()
    else:
        pipeline.run(test_mode=args.test)

if __name__ == "__main__":
    main()