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
        self.content_fetcher = ContentFetcher()
        self.summarizer = Summarizer()
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
        return {"include": [], "exclude": []}
    
    def filter_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        filter_config = self.load_filter_config()
        include_keywords = [kw.lower() for kw in filter_config.get("include", [])]
        exclude_keywords = [kw.lower() for kw in filter_config.get("exclude", [])]
        
        filtered_articles = []
        
        for article in articles:
            # 検索対象のテキストを結合
            search_text = " ".join([
                article.get('title', ''),
                article.get('abstract', ''),
                article.get('summary', ''),
                " ".join(article.get('keywords', []))
            ]).lower()
            
            # 除外キーワードチェック
            if any(keyword in search_text for keyword in exclude_keywords):
                continue
            
            # 含むキーワードチェック（指定がある場合）
            if include_keywords:
                if not any(keyword in search_text for keyword in include_keywords):
                    continue
            
            filtered_articles.append(article)
        
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
            
    def run_slack_test(self):
        """キューからの記事でSlack通知をテストする"""
        try:
            queue = self.load_queue()
            if not queue:
                print("No articles in queue for testing")
                return
                
            # キューから最大10件取得
            articles_to_notify = queue[:10]
            print(f"Testing Slack notification with {len(articles_to_notify)} articles...")
            
            self.debug_print("Articles to notify:", articles_to_notify[:2])  # 最初の2件のみ表示
            
            success = self.slack_notifier.send_notification(articles_to_notify)
            if success:
                print("Slack notification sent successfully!")
            else:
                print("Failed to send Slack notification")
                
        except Exception as e:
            print(f"Error during Slack test: {e}")

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
            self.debug_print("Articles after summarization:", [{k: v for k, v in a.items() if k in ['title', 'summary_ja', 'abstract']} for a in summarized_articles[:2]])
            
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
    parser.add_argument('--debug', action='store_true', help='Enable debug mode with detailed logging')
    parser.add_argument('--test-url', type=str, help='Test content fetching and summarization for a single URL')
    args = parser.parse_args()
    
    pipeline = PaperSummarizerPipeline(debug_mode=args.debug)
    
    if args.test_url:
        pipeline.test_single_url(args.test_url)
    elif args.slack_test:
        pipeline.run_slack_test()
    else:
        pipeline.run(test_mode=args.test)

if __name__ == "__main__":
    main()