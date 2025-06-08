import google.generativeai as genai
import os
from typing import List, Dict, Any
import time

class Summarizer:
    def __init__(self, debug_mode: bool = False):
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.debug_mode = debug_mode
        
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
        
        # 詳細ログ（デバッグモード）
        if self.debug_mode:
            print(f"  [DEBUG] Detailed input analysis:")
            print(f"    Title: '{title[:100]}{'...' if len(title) > 100 else ''}'")
            print(f"    Abstract: '{abstract[:200]}{'...' if len(abstract) > 200 else ''}'")
            print(f"    Authors: {authors}")
            print(f"    Journal: {journal}")
            print(f"    Keywords: {keywords}")
            print(f"    Total content for prompt: {len(title) + len(abstract)} chars")
        
        # 入力データの詳細ログ
        print(f"  Input validation:")
        print(f"    Title exists: {bool(title)}")
        print(f"    Abstract/Summary exists: {bool(abstract)}")
        print(f"    Content length: {len(title) + len(abstract)}")
        
        # 最小コンテンツ要件チェック
        if not title and not abstract:
            print(f"  ERROR: No title or abstract available for summarization")
            return "要約生成不可：タイトルと要旨が取得できませんでした。"
        
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
以下の科学論文について、厳密に200-250文字以内の日本語で簡潔な要約を作成してください。

【制約】
- 文字数は200-250文字厳守
- 1つのパラグラフで完結
- 簡潔で分かりやすい表現

【含める内容】
1. 研究内容の概要
2. 重要な発見・成果
3. 期待される応用

論文情報:
タイトル: {title}
著者: {author_str}
ジャーナル: {journal}

要旨:
{abstract if abstract else 'アブストラクトが取得できませんでした。タイトルから推測してください。'}

200-250文字以内の要約:"""

        try:
            print(f"  Calling Gemini API...")
            print(f"  Prompt length: {len(prompt)} characters")
            
            # API呼び出し
            if self.debug_mode:
                print(f"  [DEBUG] Full prompt being sent to Gemini:")
                print(f"  {'='*50}")
                print(prompt)
                print(f"  {'='*50}")
            
            response = self.model.generate_content(prompt)
            
            # レスポンス検証
            if self.debug_mode:
                print(f"  [DEBUG] Raw API response type: {type(response)}")
                print(f"  [DEBUG] Response attributes: {dir(response) if response else 'None'}")
                if response:
                    print(f"  [DEBUG] Response text available: {hasattr(response, 'text')}")
                    if hasattr(response, 'text'):
                        print(f"  [DEBUG] Raw response text: '{response.text}'")
            
            if not response or not hasattr(response, 'text'):
                print(f"  ERROR: Invalid API response: {response}")
                raise Exception("Invalid API response structure")
                
            summary = response.text.strip() if response.text else ""
            
            if self.debug_mode:
                print(f"  [DEBUG] Cleaned summary: '{summary}'")
                print(f"  [DEBUG] Summary length: {len(summary)} chars")
            
            if not summary:
                print(f"  ERROR: Empty summary generated")
                raise Exception("Empty summary from API")
            
            print(f"  Summary generated: {len(summary)} characters")
            print(f"  Preview: {summary[:100]}...")
            
            # 品質チェック（最小長）
            if len(summary) < 50:
                print(f"  WARNING: Summary too short ({len(summary)} chars), using fallback")
                summary = self._generate_fallback_summary(title, abstract, authors, journal)
            
            # レート制限対策
            time.sleep(1)
            
            return summary
            
        except Exception as e:
            print(f"  Error generating summary: {str(e)}")
            # エラー時のフォールバック
            fallback_summary = self._generate_fallback_summary(title, abstract, authors, journal)
            print(f"  Using fallback summary: {fallback_summary[:100]}...")
            return fallback_summary
    
    def _generate_fallback_summary(self, title: str, abstract: str, authors: List[str], journal: str) -> str:
        """API失敗時の代替要約生成"""
        # 基本的な情報組み立て
        parts = []
        
        if title:
            # タイトルから研究内容を推測
            if any(word in title.lower() for word in ['cancer', 'tumor', '腫瘍', 'がん']):
                parts.append("がん研究に関する論文。")
            elif any(word in title.lower() for word in ['quantum', '量子']):
                parts.append("量子技術に関する研究。")
            elif any(word in title.lower() for word in ['ai', 'machine learning', 'neural', '人工知能', '機械学習']):
                parts.append("AI・機械学習分野の研究。")
            elif any(word in title.lower() for word in ['climate', '気候', 'carbon', '炭素']):
                parts.append("気候・環境科学の研究。")
            elif any(word in title.lower() for word in ['crispr', 'gene', '遺伝子']):
                parts.append("遺伝子編集・バイオテクノロジーの研究。")
            else:
                parts.append(f"「{title}」に関する研究。")
        
        # 著者情報
        if authors:
            if len(authors) == 1:
                parts.append(f"{authors[0]}らによる")
            elif len(authors) <= 3:
                parts.append(f"{', '.join(authors)}らによる")
            else:
                parts.append(f"{authors[0]}ら{len(authors)}名の研究チームによる")
        
        # ジャーナル情報
        if journal:
            parts.append(f"{journal}誌に掲載された")
        
        # 要旨から重要キーワード抽出
        if abstract:
            important_words = []
            for word in ['breakthrough', 'novel', 'significant', 'innovative', 'discovery']:
                if word in abstract.lower():
                    important_words.append("革新的")
                    break
            for word in ['治療', 'therapy', 'treatment']:
                if word in abstract.lower():
                    important_words.append("治療法開発")
                    break
            for word in ['効率', 'efficiency', 'improvement']:
                if word in abstract.lower():
                    important_words.append("効率向上")
                    break
            
            if important_words:
                parts.append(f"{', '.join(important_words)}に関する")
        
        # 要旨情報を追加（HTMLクリーニングが必要でない場合のみ）
        if abstract and len(abstract) > 100:
            # HTMLタグとリンクを除去
            import re
            clean_abstract = re.sub(r'<[^>]+>', '', abstract)  # HTMLタグ除去
            clean_abstract = re.sub(r'https?://[^\s]+', '', clean_abstract)  # URL除去
            clean_abstract = re.sub(r'doi:10\.[^\s]+', '', clean_abstract)  # DOI除去
            clean_abstract = clean_abstract.strip()
            
            # 意味のあるコンテンツがあるかチェック
            meaningful_content = re.sub(r'(Nature|Science), Published online:', '', clean_abstract).strip()
            if len(meaningful_content) > 30:
                first_sentence = meaningful_content.split('.')[0].split('。')[0]
                if len(first_sentence) > 20 and len(first_sentence) < 80:
                    parts.append(f"この研究では{first_sentence}。")
        
        if len(parts) > 1:
            parts.append("の科学的知見を報告している。")
        else:
            parts.append("科学的知見を報告している。")
        
        # フォールバック要約であることを示すマーカーを追加（統計用）
        fallback_text = "".join(parts)
        if len(fallback_text) < 150:
            fallback_text += "詳細な要約はオリジナル論文を参照されたい。"
        
        return fallback_text
    
    def batch_summarize(self, articles: List[Dict[str, Any]], max_articles: int = 10) -> List[Dict[str, Any]]:
        summarized_articles = []
        successful_summaries = 0
        failed_summaries = 0
        
        print(f"Starting batch summarization for {min(len(articles), max_articles)} articles...")
        
        for i, article in enumerate(articles[:max_articles]):
            print(f"\nSummarizing article {i+1}/{min(len(articles), max_articles)}: {article.get('title', '')[:50]}...")
            
            try:
                # 記事データの事前検証
                if not isinstance(article, dict):
                    print(f"  ERROR: Invalid article data type: {type(article)}")
                    continue
                
                # summary_jaフィールドの初期化
                article['summary_ja'] = ""
                
                summary = self.summarize_article(article)
                
                # 要約結果の検証
                if not summary or not isinstance(summary, str):
                    print(f"  ERROR: Invalid summary result: {summary}")
                    summary = self._generate_fallback_summary(
                        article.get('title', ''),
                        article.get('abstract', article.get('summary', '')),
                        article.get('authors', []),
                        article.get('journal', '')
                    )
                
                article['summary_ja'] = summary
                summarized_articles.append(article)
                
                # 成功/失敗のカウント
                if any(error_phrase in summary for error_phrase in ["要約生成エラー", "要約生成不可", "詳細な要約はオリジナル論文を参照されたい"]):
                    failed_summaries += 1
                    print(f"  FAILED (fallback used): {summary[:50]}...")
                else:
                    successful_summaries += 1
                    print(f"  SUCCESS: Generated {len(summary)} char summary")
                
            except Exception as e:
                print(f"  EXCEPTION during summarization: {str(e)}")
                failed_summaries += 1
                # 例外時も記事は含める（フォールバック要約付き）
                article['summary_ja'] = self._generate_fallback_summary(
                    article.get('title', ''),
                    article.get('abstract', article.get('summary', '')),
                    article.get('authors', []),
                    article.get('journal', '')
                )
                summarized_articles.append(article)
            
        print(f"\nBatch summarization completed:")
        print(f"  Total processed: {len(summarized_articles)}")
        print(f"  Successful: {successful_summaries}")
        print(f"  Failed: {failed_summaries}")
        print(f"  Success rate: {(successful_summaries / len(summarized_articles) * 100):.1f}%" if summarized_articles else "0%")
        
        return summarized_articles