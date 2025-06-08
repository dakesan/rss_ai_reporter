import requests
from bs4 import BeautifulSoup
import time
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urlparse
import re
from journal_parsers import JournalParserFactory

class ContentFetcher:
    def __init__(self, debug_mode: bool = False):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; RSS_Paper_Summarizer/1.0; +https://github.com/your-repo)'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.debug_mode = debug_mode
        self.parser_factory = JournalParserFactory()
        
    def is_research_article(self, url: str, article: Dict[str, Any]) -> bool:
        """論文記事かどうかを判定"""
        # URLパターンで判定
        if 's41586' in url:  # Nature research articles
            return True
        elif 'd41586' in url:  # Nature news & views
            return False
        elif 'science.org/doi' in url and '/science.' in url:  # Science research
            return True
        
        # タイトルでの判定
        title = article.get('title', '').lower()
        news_keywords = ['news', 'comment', 'editorial', 'opinion', 'daily briefing', 'career', 'spotlight']
        if any(keyword in title for keyword in news_keywords):
            return False
            
        return True
        
    def _clean_html(self, text: str) -> str:
        """シンプルなHTMLタグの除去"""
        # <p>や<a>などの基本的なHTMLタグを除去
        text = re.sub(r'<[^>]+>', '', text)
        # 連続する空白を整理
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def fetch_article_details(self, article: Dict[str, Any]) -> Dict[str, Any]:
        url = article.get('link', '')
        journal = article.get('journal', '')
        
        print(f"  Fetching content from: {url}")
        
        if self.debug_mode:
            print(f"  [DEBUG] Initial article data:")
            print(f"    Title: {article.get('title', 'N/A')}")
            print(f"    Journal: {journal}")
            print(f"    Published: {article.get('published', 'N/A')}")
            print(f"    Summary from RSS: {len(article.get('summary', ''))} chars")
            print(f"    Existing abstract: {len(article.get('abstract', ''))} chars")
        
        if not url:
            print("  No URL provided, skipping content fetch")
            return article
        
        # 論文タイプの判定
        is_research = self.is_research_article(url, article)
        article['is_research_article'] = is_research
        print(f"  Article type: {'Research' if is_research else 'News/Opinion'}")
        
        # ニュース記事の場合、RSSの情報のみ使用
        if not is_research:
            print("  Skipping detailed fetch for non-research article")
            # RSSのsummaryをabstractとして使用
            if 'summary' in article and article['summary']:
                article['abstract'] = self._clean_html(article['summary'])
            return article
        
        try:
            # robots.txtを尊重するため、1秒間隔を空ける
            time.sleep(1)
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            print(f"  HTTP {response.status_code}: Content fetched successfully")
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            if self.debug_mode:
                print(f"  [DEBUG] HTML parsed successfully")
                print(f"  [DEBUG] Page title: {soup.title.string if soup.title else 'N/A'}")
                print(f"  [DEBUG] HTML content length: {len(response.content)} bytes")
            
            # ジャーナルごとに異なる構造に対応
            if journal == "Nature":
                print(f"  Using Nature parser")
                details = self._parse_nature_article(soup, article)
            elif journal == "Science":
                print(f"  Using Science parser")
                details = self._parse_science_article(soup, article)
            elif journal == "Cell":
                print(f"  Using Cell parser")
                details = self._parse_cell_article(soup, article)
            elif journal == "NEJM":
                print(f"  Using NEJM parser")
                details = self._parse_nejm_article(soup, article)
            elif journal == "PNAS":
                print(f"  Using PNAS parser")
                details = self._parse_pnas_article(soup, article)
            elif journal.startswith("arXiv"):
                print(f"  Using arXiv parser")
                details = self._parse_arxiv_article(soup, article)
            elif journal == "PLoS_ONE":
                print(f"  Using PLoS ONE parser")
                details = self._parse_plos_article(soup, article)
            else:
                print(f"  Using generic parser")
                details = self._parse_generic_article(soup, article)
                
            article.update(details)
            
            # Abstractが取得できなかった場合のフォールバック
            if not article.get('abstract') and article.get('summary'):
                print("  No abstract found, using RSS summary as fallback")
                article['abstract'] = self._clean_html(article['summary'])
            
            # 取得結果のサマリーを表示
            abstract_length = len(article.get('abstract', ''))
            authors_count = len(article.get('authors', []))
            affiliations_count = len(article.get('affiliations', []))
            keywords_count = len(article.get('keywords', []))
            
            print(f"  Content extracted: Abstract({abstract_length} chars), Authors({authors_count}), Affiliations({affiliations_count}), Keywords({keywords_count})")
            
            if self.debug_mode:
                print(f"  [DEBUG] Detailed extraction results:")
                print(f"    Abstract preview: '{article.get('abstract', '')[:150]}{'...' if abstract_length > 150 else ''}'")
                print(f"    Authors: {article.get('authors', [])}")
                print(f"    Affiliations: {article.get('affiliations', [])}")
                print(f"    Keywords: {article.get('keywords', [])}")
                
        except Exception as e:
            print(f"  Error fetching article details from {url}: {str(e)}")
            # エラー時もRSS summaryを使用
            if article.get('summary'):
                article['abstract'] = self._clean_html(article['summary'])
            
        return article
    
    def _parse_nature_article(self, soup: BeautifulSoup, article: Dict[str, Any]) -> Dict[str, Any]:
        details = {}
        
        # アブストラクトの取得 - 2025年現在のセレクタ
        abstract_selectors = [
            ('div', {'id': 'Abs1-content'}),
            ('div', {'class': 'c-article-section__content'}),
            ('section', {'aria-labelledby': 'Abs1'}),
            ('div', {'class': 'c-article-section'}),
            ('div', {'data-test': 'abstract-section'}),
            # 追加のセレクタ
            ('div', {'class': 'c-article-body__section'}),
            ('div', {'id': 'abstract'}),
            ('section', {'data-title': 'Abstract'})
        ]
        
        abstract_elem = None
        for tag, attrs in abstract_selectors:
            abstract_elem = soup.find(tag, attrs)
            if abstract_elem:
                print(f"    Abstract found with: {tag} {attrs}")
                break
        
        if not abstract_elem:
            print(f"    No abstract found with any known selectors")
        
        if abstract_elem:
            details['abstract'] = abstract_elem.get_text(strip=True)
        
        # 著者情報の詳細取得
        authors = []
        author_list = soup.find('ul', {'class': 'c-article-author-list'})
        if author_list:
            for author in author_list.find_all('li'):
                author_name = author.find('a', {'data-test': 'author-name'})
                if author_name:
                    authors.append(author_name.get_text(strip=True))
        
        if authors:
            details['authors'] = authors
        
        # 研究機関の取得
        affiliations = []
        affil_list = soup.find('ol', {'class': 'c-article-author-affiliation-list'})
        if affil_list:
            for affil in affil_list.find_all('li'):
                affil_text = affil.get_text(strip=True)
                if affil_text:
                    affiliations.append(affil_text)
        
        if affiliations:
            details['affiliations'] = affiliations
        
        # キーワードの取得
        keywords = []
        keyword_section = soup.find('div', {'class': 'c-article-subject-list'})
        if keyword_section:
            for keyword in keyword_section.find_all('a'):
                keywords.append(keyword.get_text(strip=True))
        
        if keywords:
            details['keywords'] = keywords
            
        return details
    
    def _parse_science_article(self, soup: BeautifulSoup, article: Dict[str, Any]) -> Dict[str, Any]:
        details = {}
        
        # アブストラクトの取得 - 2025年現在のセレクタ
        abstract_selectors = [
            ('div', {'class': 'section abstract'}),
            ('section', {'id': 'abstract'}),
            ('div', {'class': 'abstract-content'}),
            ('div', {'class': 'abstract'}),
            ('section', {'class': 'abstract'}),
            # 追加のセレクタ
            ('div', {'class': 'article-abstract'}),
            ('div', {'role': 'paragraph'}),
            ('div', {'data-widgetname': 'ArticleFulltext'})
        ]
        
        abstract_elem = None
        for tag, attrs in abstract_selectors:
            abstract_elem = soup.find(tag, attrs)
            if abstract_elem:
                print(f"    Abstract found with: {tag} {attrs}")
                break
        
        if not abstract_elem:
            print(f"    No abstract found with any known selectors")
        
        if abstract_elem:
            # "Abstract"というテキストを除去
            abstract_text = abstract_elem.get_text(strip=True)
            if abstract_text.startswith('Abstract'):
                abstract_text = abstract_text[8:].strip()
            details['abstract'] = abstract_text
        
        # 著者情報の詳細取得
        authors = []
        author_list = soup.find('div', {'class': 'contributors'})
        if author_list:
            for author in author_list.find_all('span', {'class': 'name'}):
                authors.append(author.get_text(strip=True))
        
        if authors:
            details['authors'] = authors
        
        # 研究機関の取得
        affiliations = []
        affil_section = soup.find('div', {'class': 'aff'})
        if affil_section:
            for affil in affil_section.find_all('span', {'class': 'institution'}):
                affiliations.append(affil.get_text(strip=True))
        
        if affiliations:
            details['affiliations'] = affiliations
            
        return details
    
    def _parse_generic_article(self, soup: BeautifulSoup, article: Dict[str, Any]) -> Dict[str, Any]:
        details = {}
        
        # 一般的なアブストラクトのパターンを試す
        abstract_patterns = [
            {'name': 'meta', 'attrs': {'name': 'description'}},
            {'name': 'meta', 'attrs': {'property': 'og:description'}},
            {'name': 'div', 'attrs': {'class': 'abstract'}},
            {'name': 'section', 'attrs': {'class': 'abstract'}},
            {'name': 'p', 'attrs': {'class': 'abstract'}}
        ]
        
        print(f"    Trying generic abstract patterns...")
        
        for pattern in abstract_patterns:
            elem = soup.find(**pattern)
            if elem:
                print(f"    Abstract found with pattern: {pattern}")
                if pattern['name'] == 'meta':
                    details['abstract'] = elem.get('content', '')
                else:
                    details['abstract'] = elem.get_text(strip=True)
                break
        
        if 'abstract' not in details:
            print(f"    No abstract found with generic patterns")
        
        # 一般的な著者パターンを試す
        authors = []
        author_patterns = [
            {'name': 'meta', 'attrs': {'name': 'author'}},
            {'name': 'span', 'attrs': {'class': 'authors'}},
            {'name': 'div', 'attrs': {'class': 'authors'}}
        ]
        
        for pattern in author_patterns:
            elems = soup.find_all(**pattern)
            for elem in elems:
                if pattern['name'] == 'meta':
                    authors.append(elem.get('content', ''))
                else:
                    authors.append(elem.get_text(strip=True))
            if authors:
                break
        
        if authors:
            details['authors'] = authors
            
        return details
    
    def _parse_cell_article(self, soup: BeautifulSoup, article: Dict[str, Any]) -> Dict[str, Any]:
        """Cell誌の記事を解析"""
        details = {}
        
        # Abstract抽出
        abstract_selectors = [
            '.summary-content p',
            '.article-section__content p',
            '.abstract p',
            '#abstract p'
        ]
        
        for selector in abstract_selectors:
            elem = soup.select_one(selector)
            if elem:
                abstract_text = elem.get_text(strip=True)
                if len(abstract_text) > 50:
                    details['abstract'] = abstract_text
                    print(f"    Found abstract: {len(abstract_text)} chars")
                    break
        
        # 著者情報抽出
        authors = []
        author_selectors = [
            '.author-group .author',
            '.authors .author-name',
            '.contributor-list .contributor'
        ]
        
        for selector in author_selectors:
            author_elems = soup.select(selector)
            if author_elems:
                for elem in author_elems:
                    name = elem.get_text(strip=True)
                    if name and name not in authors:
                        authors.append(name)
                break
        
        if authors:
            details['authors'] = authors[:10]  # 最大10名
            print(f"    Found {len(authors)} authors")
        
        return details
    
    def _parse_nejm_article(self, soup: BeautifulSoup, article: Dict[str, Any]) -> Dict[str, Any]:
        """NEJM誌の記事を解析"""
        details = {}
        
        # Abstract抽出
        abstract_selectors = [
            '.o-article-body__section--first p',
            '.abstract-content p',
            '.article-excerpt p',
            '#abstract p'
        ]
        
        for selector in abstract_selectors:
            elem = soup.select_one(selector)
            if elem:
                abstract_text = elem.get_text(strip=True)
                if len(abstract_text) > 50:
                    details['abstract'] = abstract_text
                    print(f"    Found abstract: {len(abstract_text)} chars")
                    break
        
        # 著者情報抽出
        authors = []
        author_selectors = [
            '.m-author-list .m-author-list__item',
            '.authors .author',
            '.contributor .name'
        ]
        
        for selector in author_selectors:
            author_elems = soup.select(selector)
            if author_elems:
                for elem in author_elems:
                    name = elem.get_text(strip=True)
                    if name and name not in authors:
                        authors.append(name)
                break
        
        if authors:
            details['authors'] = authors[:10]
            print(f"    Found {len(authors)} authors")
        
        return details
    
    def _parse_arxiv_article(self, soup: BeautifulSoup, article: Dict[str, Any]) -> Dict[str, Any]:
        """arXiv記事の解析"""
        details = {}
        
        # Abstract抽出
        abstract_elem = soup.find('blockquote', class_='abstract')
        if abstract_elem:
            abstract_text = abstract_elem.get_text(strip=True)
            # "Abstract:"プレフィックスを除去
            abstract_text = re.sub(r'^Abstract:\s*', '', abstract_text)
            if len(abstract_text) > 50:
                details['abstract'] = abstract_text
                print(f"    Found abstract: {len(abstract_text)} chars")
        
        # 著者情報抽出
        authors = []
        authors_elem = soup.find('div', class_='authors')
        if authors_elem:
            author_links = authors_elem.find_all('a')
            for link in author_links:
                name = link.get_text(strip=True)
                if name and name not in authors:
                    authors.append(name)
        
        if authors:
            details['authors'] = authors[:10]
            print(f"    Found {len(authors)} authors")
        
        # カテゴリ/キーワード抽出
        subjects_elem = soup.find('td', class_='tablecell subjects')
        if subjects_elem:
            categories = []
            for span in subjects_elem.find_all('span', class_='primary-subject'):
                category = span.get_text(strip=True)
                if category:
                    categories.append(category)
            if categories:
                details['keywords'] = categories
                print(f"    Found {len(categories)} categories")
        
        return details
    
    def _parse_plos_article(self, soup: BeautifulSoup, article: Dict[str, Any]) -> Dict[str, Any]:
        """PLoS ONE記事の解析"""
        details = {}
        
        # Abstract抽出
        abstract_selectors = [
            '.article-abstract p',
            '.abstract-content p',
            '#abstract p',
            '.summary p'
        ]
        
        for selector in abstract_selectors:
            elem = soup.select_one(selector)
            if elem:
                abstract_text = elem.get_text(strip=True)
                if len(abstract_text) > 50:
                    details['abstract'] = abstract_text
                    print(f"    Found abstract: {len(abstract_text)} chars")
                    break
        
        # 著者情報抽出
        authors = []
        author_selectors = [
            '.author-list .author-name',
            '.contrib-group .contrib',
            '.authors .author'
        ]
        
        for selector in author_selectors:
            author_elems = soup.select(selector)
            if author_elems:
                for elem in author_elems:
                    name = elem.get_text(strip=True)
                    if name and name not in authors:
                        authors.append(name)
                break
        
        if authors:
            details['authors'] = authors[:10]
            print(f"    Found {len(authors)} authors")
        
        # Subject areas抽出
        subjects = []
        subject_selectors = [
            '.subject-area',
            '.article-categories a',
            '.subject-list a'
        ]
        
        for selector in subject_selectors:
            subject_elems = soup.select(selector)
            if subject_elems:
                for elem in subject_elems:
                    subject = elem.get_text(strip=True)
                    if subject and subject not in subjects:
                        subjects.append(subject)
                break
        
        if subjects:
            details['keywords'] = subjects
            print(f"    Found {len(subjects)} subject areas")
        
        return details
    
    def _parse_pnas_article(self, soup: BeautifulSoup, article: Dict[str, Any]) -> Dict[str, Any]:
        """PNAS誌の記事を解析"""
        details = {}
        
        # Abstract抽出
        abstract_selectors = [
            '.section.abstract p',
            '.abstract-content p',
            '#abstract p',
            '.article-abstract p'
        ]
        
        for selector in abstract_selectors:
            elem = soup.select_one(selector)
            if elem:
                abstract_text = elem.get_text(strip=True)
                if len(abstract_text) > 50:
                    details['abstract'] = abstract_text
                    print(f"    Found abstract: {len(abstract_text)} chars")
                    break
        
        # 著者情報抽出
        authors = []
        author_selectors = [
            '.author-list .author',
            '.contributors .contributor',
            '.author-group .author-name'
        ]
        
        for selector in author_selectors:
            author_elems = soup.select(selector)
            if author_elems:
                for elem in author_elems:
                    name = elem.get_text(strip=True)
                    if name and name not in authors:
                        authors.append(name)
                break
        
        if authors:
            details['authors'] = authors[:10]
            print(f"    Found {len(authors)} authors")
        
        return details
    
    def _parse_arxiv_article(self, soup: BeautifulSoup, article: Dict[str, Any]) -> Dict[str, Any]:
        """arXiv記事の解析"""
        details = {}
        
        # Abstract抽出
        abstract_elem = soup.find('blockquote', class_='abstract')
        if abstract_elem:
            abstract_text = abstract_elem.get_text(strip=True)
            # "Abstract:"プレフィックスを除去
            abstract_text = re.sub(r'^Abstract:\s*', '', abstract_text)
            if len(abstract_text) > 50:
                details['abstract'] = abstract_text
                print(f"    Found abstract: {len(abstract_text)} chars")
        
        # 著者情報抽出
        authors = []
        authors_elem = soup.find('div', class_='authors')
        if authors_elem:
            author_links = authors_elem.find_all('a')
            for link in author_links:
                name = link.get_text(strip=True)
                if name and name not in authors:
                    authors.append(name)
        
        if authors:
            details['authors'] = authors[:10]
            print(f"    Found {len(authors)} authors")
        
        # カテゴリ/キーワード抽出
        subjects_elem = soup.find('td', class_='tablecell subjects')
        if subjects_elem:
            categories = []
            for span in subjects_elem.find_all('span', class_='primary-subject'):
                category = span.get_text(strip=True)
                if category:
                    categories.append(category)
            if categories:
                details['keywords'] = categories
                print(f"    Found {len(categories)} categories")
        
        return details
    
    def _parse_plos_article(self, soup: BeautifulSoup, article: Dict[str, Any]) -> Dict[str, Any]:
        """PLoS ONE記事の解析"""
        details = {}
        
        # Abstract抽出
        abstract_selectors = [
            '.article-abstract p',
            '.abstract-content p',
            '#abstract p',
            '.summary p'
        ]
        
        for selector in abstract_selectors:
            elem = soup.select_one(selector)
            if elem:
                abstract_text = elem.get_text(strip=True)
                if len(abstract_text) > 50:
                    details['abstract'] = abstract_text
                    print(f"    Found abstract: {len(abstract_text)} chars")
                    break
        
        # 著者情報抽出
        authors = []
        author_selectors = [
            '.author-list .author-name',
            '.contrib-group .contrib',
            '.authors .author'
        ]
        
        for selector in author_selectors:
            author_elems = soup.select(selector)
            if author_elems:
                for elem in author_elems:
                    name = elem.get_text(strip=True)
                    if name and name not in authors:
                        authors.append(name)
                break
        
        if authors:
            details['authors'] = authors[:10]
            print(f"    Found {len(authors)} authors")
        
        # Subject areas抽出
        subjects = []
        subject_selectors = [
            '.subject-area',
            '.article-categories a',
            '.subject-list a'
        ]
        
        for selector in subject_selectors:
            subject_elems = soup.select(selector)
            if subject_elems:
                for elem in subject_elems:
                    subject = elem.get_text(strip=True)
                    if subject and subject not in subjects:
                        subjects.append(subject)
                break
        
        if subjects:
            details['keywords'] = subjects
            print(f"    Found {len(subjects)} subject areas")
        
        return details