import google.generativeai as genai
import os
from typing import List, Dict, Any
import time

class Summarizer:
    def __init__(self):
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
    def summarize_article(self, article: Dict[str, Any]) -> str:
        # 論文情報をプロンプト用にフォーマット
        title = article.get('title', '')
        abstract = article.get('abstract', article.get('summary', ''))
        authors = article.get('authors', [])
        journal = article.get('journal', '')
        keywords = article.get('keywords', [])
        
        print(f"  Summarizing: {title[:60]}...")
        print(f"  Abstract available: {len(abstract)} characters")
        print(f"  Authors: {len(authors)} found")
        print(f"  Keywords: {len(keywords)} found")
        
        # 著者情報の整形
        if authors:
            if len(authors) > 3:
                author_str = f"{', '.join(authors[:3])} 他"
            else:
                author_str = ', '.join(authors)
        else:
            author_str = "著者情報なし"
        
        # プロンプトの構築
        prompt = f"""
以下の科学論文について、200-300文字程度の日本語で要約を作成してください。
要約には以下の要素を含めてください：
1. どのような研究か（研究の概要）
2. 何が新しいか、または重要か（革新性・重要性）
3. どのような影響や応用が期待されるか（将来への影響）

論文情報:
タイトル: {title}
著者: {author_str}
ジャーナル: {journal}
キーワード: {', '.join(keywords) if keywords else 'なし'}

要旨:
{abstract if abstract else 'アブストラクトが取得できませんでした。タイトルから推測してください。'}

要約:"""

        try:
            print(f"  Calling Gemini API...")
            # API呼び出し
            response = self.model.generate_content(prompt)
            summary = response.text.strip()
            
            print(f"  Summary generated: {len(summary)} characters")
            print(f"  Preview: {summary[:100]}...")
            
            # レート制限対策
            time.sleep(1)
            
            return summary
            
        except Exception as e:
            print(f"  Error generating summary: {str(e)}")
            # エラー時のフォールバック
            fallback_summary = f"要約生成エラー。{title[:100]}... についての論文です。"
            print(f"  Using fallback summary: {fallback_summary}")
            return fallback_summary
    
    def batch_summarize(self, articles: List[Dict[str, Any]], max_articles: int = 10) -> List[Dict[str, Any]]:
        summarized_articles = []
        successful_summaries = 0
        failed_summaries = 0
        
        print(f"Starting batch summarization for {min(len(articles), max_articles)} articles...")
        
        for i, article in enumerate(articles[:max_articles]):
            print(f"\nSummarizing article {i+1}/{min(len(articles), max_articles)}: {article.get('title', '')[:50]}...")
            
            summary = self.summarize_article(article)
            article['summary_ja'] = summary
            summarized_articles.append(article)
            
            # 成功/失敗のカウント
            if "要約生成エラー" in summary:
                failed_summaries += 1
            else:
                successful_summaries += 1
            
        print(f"\nBatch summarization completed: {successful_summaries} successful, {failed_summaries} failed")
        return summarized_articles