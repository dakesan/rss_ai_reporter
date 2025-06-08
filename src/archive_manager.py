#!/usr/bin/env python3
"""
データアーカイブ管理システム - 処理済み論文の圧縮保存
"""
import json
import gzip
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

class ArchiveManager:
    """処理済み論文のアーカイブ管理"""
    
    def __init__(self, archive_dir: str = "data/archive"):
        self.archive_dir = archive_dir
        self.daily_archive_limit = 50  # 1日あたりの最大アーカイブ件数
        os.makedirs(archive_dir, exist_ok=True)
    
    def archive_processed_articles(self, articles: List[Dict[str, Any]]) -> int:
        """処理済み記事をアーカイブに保存"""
        if not articles:
            return 0
        
        # 日付別にアーカイブファイルを作成
        today = datetime.now().strftime("%Y%m%d")
        archive_file = os.path.join(self.archive_dir, f"processed_{today}.jsonl.gz")
        
        archived_count = 0
        
        # アーカイブ用のデータを準備
        archive_data = []
        for article in articles:
            # 必要な情報のみを抽出してサイズ削減
            archived_article = {
                "id": article.get("id"),
                "title": article.get("title"),
                "journal": article.get("journal"),
                "authors": article.get("authors", [])[:3],  # 最大3名まで
                "summary_ja": article.get("summary_ja", "")[:200],  # 200文字まで
                "published": article.get("published"),
                "processed_at": datetime.now().isoformat(),
                "priority": article.get("priority"),
                "link": article.get("link")
            }
            archive_data.append(archived_article)
        
        # 圧縮して保存
        try:
            with gzip.open(archive_file, 'at', encoding='utf-8') as f:
                for article in archive_data:
                    f.write(json.dumps(article, ensure_ascii=False) + '\\n')
                    archived_count += 1
            
            print(f"📦 Archived {archived_count} processed articles to {archive_file}")
            return archived_count
            
        except Exception as e:
            print(f"Error archiving articles: {e}")
            return 0
    
    def get_archive_stats(self, days: int = 30) -> Dict[str, Any]:
        """アーカイブの統計情報を取得"""
        stats = {
            "total_files": 0,
            "total_articles": 0,
            "size_mb": 0.0,
            "date_range": [],
            "files": []
        }
        
        if not os.path.exists(self.archive_dir):
            return stats
        
        # アーカイブファイルをスキャン
        for filename in os.listdir(self.archive_dir):
            if filename.endswith('.jsonl.gz'):
                filepath = os.path.join(self.archive_dir, filename)
                file_stats = os.stat(filepath)
                
                # ファイル情報を収集
                file_info = {
                    "filename": filename,
                    "size_mb": file_stats.st_size / (1024 * 1024),
                    "modified": datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
                    "article_count": self._count_articles_in_archive(filepath)
                }
                
                stats["files"].append(file_info)
                stats["total_files"] += 1
                stats["total_articles"] += file_info["article_count"]
                stats["size_mb"] += file_info["size_mb"]
        
        # 日付範囲を設定
        if stats["files"]:
            dates = [f["modified"][:10] for f in stats["files"]]
            stats["date_range"] = [min(dates), max(dates)]
        
        return stats
    
    def _count_articles_in_archive(self, filepath: str) -> int:
        """アーカイブファイル内の記事数をカウント"""
        try:
            with gzip.open(filepath, 'rt', encoding='utf-8') as f:
                return sum(1 for line in f if line.strip())
        except Exception:
            return 0
    
    def search_archive(self, query: str, days: int = 30) -> List[Dict[str, Any]]:
        """アーカイブから記事を検索"""
        results = []
        query_lower = query.lower()
        
        # 最近のアーカイブファイルを検索
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for filename in os.listdir(self.archive_dir):
            if not filename.endswith('.jsonl.gz'):
                continue
                
            filepath = os.path.join(self.archive_dir, filename)
            file_stats = os.stat(filepath)
            
            # 指定期間内のファイルのみ検索
            if datetime.fromtimestamp(file_stats.st_mtime) < cutoff_date:
                continue
            
            try:
                with gzip.open(filepath, 'rt', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        
                        try:
                            article = json.loads(line)
                            
                            # タイトルまたは要約に検索クエリが含まれているかチェック
                            title = article.get('title', '').lower()
                            summary = article.get('summary_ja', '').lower()
                            
                            if query_lower in title or query_lower in summary:
                                results.append(article)
                                
                        except json.JSONDecodeError:
                            continue
                            
            except Exception as e:
                print(f"Error searching archive {filename}: {e}")
                continue
        
        return results
    
    def cleanup_old_archives(self, keep_days: int = 90) -> int:
        """古いアーカイブファイルを削除"""
        if not os.path.exists(self.archive_dir):
            return 0
        
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        removed_count = 0
        
        for filename in os.listdir(self.archive_dir):
            if not filename.endswith('.jsonl.gz'):
                continue
                
            filepath = os.path.join(self.archive_dir, filename)
            file_stats = os.stat(filepath)
            
            if datetime.fromtimestamp(file_stats.st_mtime) < cutoff_date:
                try:
                    os.remove(filepath)
                    removed_count += 1
                    print(f"🗑️  Removed old archive: {filename}")
                except Exception as e:
                    print(f"Error removing {filename}: {e}")
        
        return removed_count
    
    def export_monthly_summary(self, year: int, month: int) -> Optional[str]:
        """月次サマリーをエクスポート"""
        month_str = f"{year:04d}{month:02d}"
        summary_file = os.path.join(self.archive_dir, f"summary_{month_str}.json")
        
        monthly_stats = {
            "year": year,
            "month": month,
            "total_articles": 0,
            "journals": {},
            "top_keywords": {},
            "generated_at": datetime.now().isoformat()
        }
        
        # その月のアーカイブファイルを処理
        for filename in os.listdir(self.archive_dir):
            if not filename.startswith(f"processed_{month_str}") or not filename.endswith('.jsonl.gz'):
                continue
            
            filepath = os.path.join(self.archive_dir, filename)
            
            try:
                with gzip.open(filepath, 'rt', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        
                        try:
                            article = json.loads(line)
                            monthly_stats["total_articles"] += 1
                            
                            # ジャーナル統計
                            journal = article.get('journal', 'Unknown')
                            monthly_stats["journals"][journal] = monthly_stats["journals"].get(journal, 0) + 1
                            
                            # キーワード分析（簡易版）
                            title_words = article.get('title', '').lower().split()
                            for word in title_words:
                                if len(word) > 4:  # 4文字以上の単語のみ
                                    monthly_stats["top_keywords"][word] = monthly_stats["top_keywords"].get(word, 0) + 1
                                    
                        except json.JSONDecodeError:
                            continue
                            
            except Exception as e:
                print(f"Error processing {filename} for summary: {e}")
                continue
        
        # サマリーファイルを保存
        try:
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(monthly_stats, f, indent=2, ensure_ascii=False)
            
            print(f"📊 Monthly summary exported: {summary_file}")
            return summary_file
            
        except Exception as e:
            print(f"Error exporting monthly summary: {e}")
            return None