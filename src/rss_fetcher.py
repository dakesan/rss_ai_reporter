import feedparser
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any
import time

class RSSFetcher:
    def __init__(self, 
                 checkpoint_file: str = "data/last_check.json", 
                 feeds_config_file: str = "data/feeds_config.json",
                 max_age_days: int = 30):
        self.checkpoint_file = checkpoint_file
        self.feeds_config_file = feeds_config_file
        self.max_age_days = max_age_days
        self.feeds_config = self.load_feeds_config()
        
    def load_feeds_config(self) -> Dict[str, Any]:
        """フィード設定をJSONファイルから読み込み"""
        if os.path.exists(self.feeds_config_file):
            with open(self.feeds_config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # デフォルト設定（後方互換性）
            return {
                "feeds": {
                    "Nature": {
                        "url": "https://www.nature.com/nature.rss",
                        "enabled": True,
                        "priority": "high",
                        "parser_type": "nature"
                    },
                    "Science": {
                        "url": "https://www.science.org/rss/news_current.xml", 
                        "enabled": True,
                        "priority": "high",
                        "parser_type": "science"
                    }
                }
            }
    
    def get_enabled_feeds(self) -> Dict[str, Dict[str, Any]]:
        """有効なフィードのみを取得"""
        enabled_feeds = {}
        for name, config in self.feeds_config.get("feeds", {}).items():
            if config.get("enabled", True):
                enabled_feeds[name] = config
        return enabled_feeds
    
    def load_checkpoint(self) -> Dict[str, Any]:
        if os.path.exists(self.checkpoint_file):
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"last_check": None, "seen_articles": {}}
    
    def save_checkpoint(self, checkpoint: Dict[str, Any]):
        os.makedirs(os.path.dirname(self.checkpoint_file), exist_ok=True)
        with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(checkpoint, f, indent=2, ensure_ascii=False)
    
    def cleanup_old_entries(self, seen_articles: Dict[str, str]) -> Dict[str, str]:
        """古いエントリを削除してメモリ使用量を最適化"""
        cutoff_date = datetime.now() - timedelta(days=self.max_age_days)
        cleaned_articles = {}
        removed_count = 0
        
        for article_id, timestamp_str in seen_articles.items():
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
                if timestamp >= cutoff_date:
                    cleaned_articles[article_id] = timestamp_str
                else:
                    removed_count += 1
            except ValueError:
                # 無効な日付形式の場合はスキップ（削除）
                removed_count += 1
                continue
        
        if removed_count > 0:
            print(f"Cleaned up {removed_count} old entries from checkpoint")
        
        return cleaned_articles
    
    def fetch_new_articles(self) -> List[Dict[str, Any]]:
        checkpoint = self.load_checkpoint()
        seen_articles = checkpoint.get("seen_articles", {})
        
        # 古いエントリをクリーンアップ
        seen_articles = self.cleanup_old_entries(seen_articles)
        
        new_articles = []
        enabled_feeds = self.get_enabled_feeds()
        global_settings = self.feeds_config.get("global_settings", {})
        request_delay = global_settings.get("request_delay_seconds", 1)
        
        for journal_name, feed_config in enabled_feeds.items():
            feed_url = feed_config["url"]
            try:
                print(f"Fetching RSS from {journal_name}...")
                feed = feedparser.parse(feed_url)
                
                if feed.bozo:
                    print(f"Error parsing {journal_name} feed: {feed.bozo_exception}")
                    continue
                
                for entry in feed.entries:
                    article_id = entry.get('id', entry.get('link', ''))
                    
                    if article_id and article_id not in seen_articles:
                        article = {
                            'id': article_id,
                            'journal': journal_name,
                            'title': entry.get('title', ''),
                            'link': entry.get('link', ''),
                            'published': entry.get('published', ''),
                            'summary': entry.get('summary', ''),
                            'authors': self._extract_authors(entry),
                            'doi': self._extract_doi(entry),
                            'parser_type': feed_config.get('parser_type', 'default'),
                            'feed_priority': feed_config.get('priority', 'normal')
                        }
                        
                        new_articles.append(article)
                        seen_articles[article_id] = datetime.now().isoformat()
                
                # RSS取得間隔を設定値分空ける
                time.sleep(request_delay)
                
            except Exception as e:
                print(f"Error fetching {journal_name} RSS: {str(e)}")
        
        # チェックポイントを更新
        checkpoint["last_check"] = datetime.now().isoformat()
        checkpoint["seen_articles"] = seen_articles
        self.save_checkpoint(checkpoint)
        
        return new_articles
    
    def _extract_authors(self, entry: Dict[str, Any]) -> List[str]:
        authors = []
        
        # feedparserの標準的な著者情報取得
        if hasattr(entry, 'authors'):
            for author in entry.authors:
                if 'name' in author:
                    authors.append(author['name'])
        
        # DCタグからの取得
        if hasattr(entry, 'dc_creator'):
            authors.append(entry.dc_creator)
        
        # 著者情報がない場合
        if not authors and hasattr(entry, 'author'):
            authors.append(entry.author)
            
        return authors
    
    def _extract_doi(self, entry: Dict[str, Any]) -> str:
        # DOIの抽出（リンクやIDから）
        doi = ""
        
        # dc:identifierタグから
        if hasattr(entry, 'dc_identifier'):
            if 'doi.org' in entry.dc_identifier:
                doi = entry.dc_identifier
        
        # linkから抽出
        if not doi and 'link' in entry:
            if 'doi.org' in entry['link']:
                doi = entry['link']
            elif '/doi/' in entry['link']:
                parts = entry['link'].split('/doi/')
                if len(parts) > 1:
                    doi = f"https://doi.org/{parts[1].split('?')[0]}"
        
        return doi