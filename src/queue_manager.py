#!/usr/bin/env python3
"""
キュー管理システム - 優先度機能とバッチ処理の改善
"""
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from enum import Enum

class Priority(Enum):
    """論文の優先度レベル"""
    URGENT = 1      # 緊急（特定キーワード）
    HIGH = 2        # 高（高インパクトジャーナル）
    NORMAL = 3      # 通常
    LOW = 4         # 低（News記事など）

class QueueManager:
    """改良されたキュー管理システム"""
    
    def __init__(self, queue_file: str = "data/queue.json"):
        self.queue_file = queue_file
        self.priority_keywords = {
            Priority.URGENT: ["breakthrough", "Nobel", "clinical trial", "COVID", "pandemic"],
            Priority.HIGH: ["CRISPR", "quantum", "AI", "machine learning", "cancer", "vaccine"]
        }
        self.high_impact_journals = ["Nature", "Science", "Cell", "NEJM"]
    
    def load_queue(self) -> List[Dict[str, Any]]:
        """キューからアイテムを読み込み"""
        if os.path.exists(self.queue_file):
            with open(self.queue_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def save_queue(self, queue: List[Dict[str, Any]]):
        """キューをファイルに保存（サイズ制限付き）"""
        # サイズ制限：最大500件
        MAX_QUEUE_SIZE = 500
        if len(queue) > MAX_QUEUE_SIZE:
            # 優先度順にソートして上位のみ保持
            queue_sorted = sorted(queue, key=lambda x: (x.get('priority', 999), x.get('added_at', '')))
            queue = queue_sorted[:MAX_QUEUE_SIZE]
            print(f"Queue size limited to {MAX_QUEUE_SIZE} items")
        
        os.makedirs(os.path.dirname(self.queue_file), exist_ok=True)
        with open(self.queue_file, 'w', encoding='utf-8') as f:
            json.dump(queue, f, indent=2, ensure_ascii=False)
    
    def calculate_priority(self, article: Dict[str, Any]) -> Priority:
        """記事の優先度を計算"""
        title = article.get('title', '').lower()
        abstract = article.get('abstract', '').lower()
        journal = article.get('journal', '')
        
        search_text = f"{title} {abstract}"
        
        # 緊急キーワードをチェック
        for keyword in self.priority_keywords[Priority.URGENT]:
            if keyword.lower() in search_text:
                return Priority.URGENT
        
        # 高優先度キーワードをチェック
        for keyword in self.priority_keywords[Priority.HIGH]:
            if keyword.lower() in search_text:
                return Priority.HIGH
        
        # 高インパクトジャーナルをチェック
        if journal in self.high_impact_journals:
            return Priority.HIGH
        
        # Newsやd41586記事は低優先度
        if 'd41586' in article.get('link', ''):
            return Priority.LOW
            
        return Priority.NORMAL
    
    def add_articles(self, articles: List[Dict[str, Any]]) -> int:
        """記事をキューに追加（優先度付き）"""
        queue = self.load_queue()
        added_count = 0
        
        # 既存記事のIDセットを作成
        existing_ids = {item.get('id') for item in queue}
        
        for article in articles:
            article_id = article.get('id')
            if not article_id or article_id in existing_ids:
                continue
            
            # 優先度を計算して追加
            priority = self.calculate_priority(article)
            article['priority'] = priority.value
            article['priority_name'] = priority.name
            article['added_at'] = datetime.now().isoformat()
            
            queue.append(article)
            existing_ids.add(article_id)
            added_count += 1
        
        # 優先度順にソート（数値が小さいほど優先度が高い）
        queue.sort(key=lambda x: (x.get('priority', Priority.NORMAL.value), x.get('added_at', '')))
        
        self.save_queue(queue)
        return added_count
    
    def get_batch(self, batch_size: int = 10, max_age_days: int = 7) -> List[Dict[str, Any]]:
        """バッチ処理用の記事を取得（優先度順）"""
        queue = self.load_queue()
        
        # 古すぎる記事を除外
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        current_articles = []
        
        for article in queue:
            try:
                added_at = datetime.fromisoformat(article.get('added_at', ''))
                if added_at >= cutoff_date:
                    current_articles.append(article)
            except ValueError:
                # 日付形式が無効な場合はそのまま含める
                current_articles.append(article)
        
        # バッチサイズ分を取得
        batch = current_articles[:batch_size]
        remaining = current_articles[batch_size:]
        
        # 残りのキューを保存
        self.save_queue(remaining)
        
        return batch
    
    def get_priority_stats(self) -> Dict[str, int]:
        """キュー内の優先度別統計を取得"""
        queue = self.load_queue()
        stats = {priority.name: 0 for priority in Priority}
        
        for article in queue:
            priority_value = article.get('priority', Priority.NORMAL.value)
            try:
                priority = Priority(priority_value)
                stats[priority.name] += 1
            except ValueError:
                stats[Priority.NORMAL.name] += 1
        
        return stats
    
    def cleanup_old_items(self, max_age_days: int = 30) -> int:
        """古いアイテムをクリーンアップ"""
        queue = self.load_queue()
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        
        cleaned_queue = []
        removed_count = 0
        
        for article in queue:
            try:
                added_at = datetime.fromisoformat(article.get('added_at', ''))
                if added_at >= cutoff_date:
                    cleaned_queue.append(article)
                else:
                    removed_count += 1
            except ValueError:
                # 日付形式が無効な場合は削除
                removed_count += 1
        
        if removed_count > 0:
            self.save_queue(cleaned_queue)
            print(f"Cleaned up {removed_count} old items from queue")
        
        return removed_count
    
    def get_queue_info(self) -> Dict[str, Any]:
        """キューの詳細情報を取得"""
        queue = self.load_queue()
        priority_stats = self.get_priority_stats()
        
        return {
            "total_items": len(queue),
            "priority_breakdown": priority_stats,
            "oldest_item": min((item.get('added_at', '') for item in queue), default=None),
            "newest_item": max((item.get('added_at', '') for item in queue), default=None)
        }

    def refilter_queue(self, filter_config: Dict[str, Any]) -> Dict[str, int]:
        """既存キューエントリーを現在のフィルター設定で再評価"""
        queue = self.load_queue()
        
        include_keywords = [kw.lower() for kw in filter_config.get("include", [])]
        exclude_keywords = [kw.lower() for kw in filter_config.get("exclude", [])]
        research_only = filter_config.get("research_only", True)
        article_types = filter_config.get("article_types", {})
        
        filtered_queue = []
        stats = {
            "total_before": len(queue),
            "removed_research_filter": 0,
            "removed_keyword_filter": 0,
            "removed_article_type": 0,
            "total_after": 0
        }
        
        for article in queue:
            # 論文フィルター
            if research_only:
                url = article.get('link', '')
                if 'd41586' in url:  # Nature news
                    stats["removed_research_filter"] += 1
                    continue
            
            # 記事タイプフィルター
            if article_types:
                # URLパターンから記事タイプを推測
                url = article.get('link', '')
                is_news = any(pattern in url for pattern in ['d41586', 'news', 'opinion'])
                is_editorial = 'editorial' in url.lower()
                
                if is_news and not article_types.get("news", False):
                    stats["removed_article_type"] += 1
                    continue
                if is_editorial and not article_types.get("editorial", False):
                    stats["removed_article_type"] += 1
                    continue
            
            # 検索対象のテキストを結合
            search_text = " ".join([
                article.get('title', ''),
                article.get('summary', ''),
                article.get('abstract', ''),
                " ".join(article.get('authors', []))
            ]).lower()
            
            # 除外キーワードチェック
            if any(keyword in search_text for keyword in exclude_keywords):
                stats["removed_keyword_filter"] += 1
                continue
            
            # 含有キーワードチェック
            if include_keywords:
                if not any(keyword in search_text for keyword in include_keywords):
                    stats["removed_keyword_filter"] += 1
                    continue
            
            # フィルターを通過
            filtered_queue.append(article)
        
        stats["total_after"] = len(filtered_queue)
        
        # フィルター済みキューを保存
        self.save_queue(filtered_queue)
        
        return stats

    def remove_disabled_feeds(self, feeds_config: Dict[str, Any]) -> Dict[str, int]:
        """無効化されたフィードのエントリーを削除"""
        queue = self.load_queue()
        
        # 有効なフィード一覧を取得
        enabled_feeds = set()
        for feed_name, feed_config in feeds_config.get("feeds", {}).items():
            if feed_config.get("enabled", True):
                enabled_feeds.add(feed_name)
        
        filtered_queue = []
        stats = {
            "total_before": len(queue),
            "removed_disabled_feeds": 0,
            "total_after": 0
        }
        
        for article in queue:
            journal = article.get('journal', '')
            if journal and journal not in enabled_feeds:
                stats["removed_disabled_feeds"] += 1
                continue
            
            filtered_queue.append(article)
        
        stats["total_after"] = len(filtered_queue)
        
        # フィルター済みキューを保存
        self.save_queue(filtered_queue)
        
        return stats