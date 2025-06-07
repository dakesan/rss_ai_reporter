import feedparser
import json
import os
from datetime import datetime
from typing import List, Dict, Any
import time

class RSSFetcher:
    def __init__(self, checkpoint_file: str = "data/last_check.json"):
        self.checkpoint_file = checkpoint_file
        self.feeds = {
            "Nature": "https://www.nature.com/nature.rss",
            "Science": "https://www.science.org/rss/news_current.xml"
        }
        
    def load_checkpoint(self) -> Dict[str, Any]:
        if os.path.exists(self.checkpoint_file):
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"last_check": None, "seen_articles": {}}
    
    def save_checkpoint(self, checkpoint: Dict[str, Any]):
        os.makedirs(os.path.dirname(self.checkpoint_file), exist_ok=True)
        with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(checkpoint, f, indent=2, ensure_ascii=False)
    
    def fetch_new_articles(self) -> List[Dict[str, Any]]:
        checkpoint = self.load_checkpoint()
        seen_articles = checkpoint.get("seen_articles", {})
        new_articles = []
        
        for journal, feed_url in self.feeds.items():
            try:
                print(f"Fetching RSS from {journal}...")
                feed = feedparser.parse(feed_url)
                
                if feed.bozo:
                    print(f"Error parsing {journal} feed: {feed.bozo_exception}")
                    continue
                
                for entry in feed.entries:
                    article_id = entry.get('id', entry.get('link', ''))
                    
                    if article_id and article_id not in seen_articles:
                        article = {
                            'id': article_id,
                            'journal': journal,
                            'title': entry.get('title', ''),
                            'link': entry.get('link', ''),
                            'published': entry.get('published', ''),
                            'summary': entry.get('summary', ''),
                            'authors': self._extract_authors(entry),
                            'doi': self._extract_doi(entry)
                        }
                        
                        new_articles.append(article)
                        seen_articles[article_id] = datetime.now().isoformat()
                
                # RSS取得間隔を1秒空ける
                time.sleep(1)
                
            except Exception as e:
                print(f"Error fetching {journal} RSS: {str(e)}")
        
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