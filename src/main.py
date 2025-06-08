#!/usr/bin/env python3
import sys
import json
import os
import argparse
from typing import List, Dict, Any
from datetime import datetime

from rss_fetcher import RSSFetcher
from content_fetcher import ContentFetcher
from summarizer import Summarizer
from slack_notifier import SlackNotifier

class PaperSummarizerPipeline:
    def __init__(self, debug_mode: bool = False):
        self.debug_mode = debug_mode
        self.rss_fetcher = RSSFetcher()
        self.content_fetcher = ContentFetcher(debug_mode=debug_mode)
        self.summarizer = Summarizer(debug_mode=debug_mode)
        self.slack_notifier = SlackNotifier()
        self.queue_file = "data/queue.json"
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
        
    def load_queue(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.queue_file):
            with open(self.queue_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def save_queue(self, queue: List[Dict[str, Any]]):
        os.makedirs(os.path.dirname(self.queue_file), exist_ok=True)
        with open(self.queue_file, 'w', encoding='utf-8') as f:
            json.dump(queue, f, indent=2, ensure_ascii=False)
    
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
            queue = self.load_queue()
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
            queue = self.load_queue()
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
            queue = self.load_queue()
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

    def run(self, test_mode: bool = False):
        try:
            print("Starting RSS Paper Summarizer...")
            
            # 1. RSS取得
            print("\n1. Fetching RSS feeds...")
            new_articles = self.rss_fetcher.fetch_new_articles()
            print(f"Found {len(new_articles)} new articles")
            self.debug_print("New articles sample:", new_articles[:2] if new_articles else [])
            
            # 2. キューから未処理記事を取得
            queue = self.load_queue()
            total_articles = queue + new_articles
            
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
                self.save_queue([])
                return
            
            # 4. 処理する記事数を決定（最大10件）
            articles_to_process = filtered_articles[:10]
            remaining_articles = filtered_articles[10:]
            
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
            
            # 8. キューを更新
            self.save_queue(remaining_articles)
            print(f"\nRemaining articles in queue: {len(remaining_articles)}")
            
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
    args = parser.parse_args()
    
    pipeline = PaperSummarizerPipeline(debug_mode=args.debug)
    
    if args.test_url:
        pipeline.test_single_url(args.test_url)
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