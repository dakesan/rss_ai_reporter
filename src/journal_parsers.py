#!/usr/bin/env python3
"""
ジャーナル別パーサー - 各ジャーナルの特定の構造に対応
"""
import requests
from bs4 import BeautifulSoup
import re
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod
import time

class BaseJournalParser(ABC):
    """ジャーナルパーサーの基底クラス"""
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'RSS AI Reporter/1.0 (Educational Purpose)'
        })
    
    @abstractmethod
    def parse_article_details(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """記事の詳細を解析"""
        pass
    
    @abstractmethod
    def is_research_article(self, article: Dict[str, Any]) -> bool:
        """研究論文かどうかを判定"""
        pass
    
    def debug_print(self, message: str, data: Any = None):
        """デバッグ出力"""
        if self.debug:
            print(f"[{self.__class__.__name__}] {message}")
            if data:
                print(f"  Data: {data}")
    
    def safe_request(self, url: str, timeout: int = 10) -> Optional[BeautifulSoup]:
        """安全なHTTPリクエスト"""
        try:
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            self.debug_print(f"Request failed for {url}: {e}")
            return None

class NatureParser(BaseJournalParser):
    """Nature誌専用パーサー"""
    
    def is_research_article(self, article: Dict[str, Any]) -> bool:
        """Nature研究論文の判定"""
        url = article.get('link', '')
        return 's41586' in url and 'd41586' not in url
    
    def parse_article_details(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Nature記事の詳細解析"""
        url = article.get('link', '')
        if not url:
            return article
        
        self.debug_print(f"Parsing Nature article: {url}")
        
        soup = self.safe_request(url)
        if not soup:
            return article
        
        # Abstract抽出
        abstract = self._extract_nature_abstract(soup)
        if abstract:
            article['abstract'] = abstract
        
        # 著者情報抽出
        authors = self._extract_nature_authors(soup)
        if authors:
            article['authors'] = authors
        
        # キーワード抽出
        keywords = self._extract_nature_keywords(soup)
        if keywords:
            article['keywords'] = keywords
        
        return article
    
    def _extract_nature_abstract(self, soup: BeautifulSoup) -> str:
        """Natureのアブストラクト抽出"""
        selectors = [
            'div[data-test="abstract-section"] p',
            '.c-article-section__content p',
            '#abstract-content p',
            '.c-article-body__section p'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                abstract_parts = []
                for elem in elements[:3]:  # 最初の3つのパラグラフ
                    text = elem.get_text(strip=True)
                    if text and len(text) > 50:
                        abstract_parts.append(text)
                
                if abstract_parts:
                    return ' '.join(abstract_parts)
        
        return ""
    
    def _extract_nature_authors(self, soup: BeautifulSoup) -> List[str]:
        """Nature著者情報抽出"""
        authors = []
        
        # 複数のセレクタを試行
        author_selectors = [
            'span[data-test="author-name"]',
            '.c-article-author-list__item .c-author-list__name',
            '.c-author-list__name',
            '.author-name'
        ]
        
        for selector in author_selectors:
            author_elements = soup.select(selector)
            if author_elements:
                for elem in author_elements:
                    name = elem.get_text(strip=True)
                    if name and name not in authors:
                        authors.append(name)
                break
        
        return authors[:10]  # 最大10名まで
    
    def _extract_nature_keywords(self, soup: BeautifulSoup) -> List[str]:
        """Natureキーワード抽出"""
        keywords = []
        
        # subject areas/keywords
        keyword_selectors = [
            '.c-subject-list__item a',
            '.c-article-subject-list a',
            '.subject a'
        ]
        
        for selector in keyword_selectors:
            elements = soup.select(selector)
            if elements:
                for elem in elements:
                    keyword = elem.get_text(strip=True)
                    if keyword and keyword not in keywords:
                        keywords.append(keyword)
                break
        
        return keywords

class ScienceParser(BaseJournalParser):
    """Science誌専用パーサー"""
    
    def is_research_article(self, article: Dict[str, Any]) -> bool:
        """Science研究論文の判定"""
        url = article.get('link', '')
        return 'doi/10.1126/science' in url
    
    def parse_article_details(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Science記事の詳細解析"""
        url = article.get('link', '')
        if not url:
            return article
        
        self.debug_print(f"Parsing Science article: {url}")
        
        soup = self.safe_request(url)
        if not soup:
            return article
        
        # Abstract抽出
        abstract = self._extract_science_abstract(soup)
        if abstract:
            article['abstract'] = abstract
        
        # 著者情報抽出  
        authors = self._extract_science_authors(soup)
        if authors:
            article['authors'] = authors
        
        return article
    
    def _extract_science_abstract(self, soup: BeautifulSoup) -> str:
        """Scienceのアブストラクト抽出"""
        selectors = [
            '.article-abstract-content p',
            '.abstract-content p',
            '#abstract p',
            '.executive-summary p'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                abstract_text = ' '.join([elem.get_text(strip=True) for elem in elements])
                if len(abstract_text) > 50:
                    return abstract_text
        
        return ""
    
    def _extract_science_authors(self, soup: BeautifulSoup) -> List[str]:
        """Science著者情報抽出"""
        authors = []
        
        author_selectors = [
            '.authors-list .author-name',
            '.author .author-name',
            '.contrib-group .contrib .name'
        ]
        
        for selector in author_selectors:
            author_elements = soup.select(selector)
            if author_elements:
                for elem in author_elements:
                    name = elem.get_text(strip=True)
                    if name and name not in authors:
                        authors.append(name)
                break
        
        return authors[:10]

class CellParser(BaseJournalParser):
    """Cell誌専用パーサー"""
    
    def is_research_article(self, article: Dict[str, Any]) -> bool:
        """Cell研究論文の判定"""
        url = article.get('link', '')
        return 'cell/fulltext' in url
    
    def parse_article_details(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Cell記事の詳細解析"""
        url = article.get('link', '')
        if not url:
            return article
        
        self.debug_print(f"Parsing Cell article: {url}")
        
        soup = self.safe_request(url)
        if not soup:
            return article
        
        # Abstract抽出
        abstract = self._extract_cell_abstract(soup)
        if abstract:
            article['abstract'] = abstract
        
        # 著者情報抽出
        authors = self._extract_cell_authors(soup)
        if authors:
            article['authors'] = authors
        
        return article
    
    def _extract_cell_abstract(self, soup: BeautifulSoup) -> str:
        """Cellのアブストラクト抽出"""
        selectors = [
            '.abstract-content p',
            '#abstract p',
            '.summary p'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                abstract_text = ' '.join([elem.get_text(strip=True) for elem in elements])
                if len(abstract_text) > 50:
                    return abstract_text
        
        return ""
    
    def _extract_cell_authors(self, soup: BeautifulSoup) -> List[str]:
        """Cell著者情報抽出"""
        authors = []
        
        author_selectors = [
            '.author-group .author',
            '.author-list .author-name'
        ]
        
        for selector in author_selectors:
            author_elements = soup.select(selector)
            if author_elements:
                for elem in author_elements:
                    name = elem.get_text(strip=True)
                    if name and name not in authors:
                        authors.append(name)
                break
        
        return authors[:10]

class ArxivParser(BaseJournalParser):
    """arXiv専用パーサー"""
    
    def is_research_article(self, article: Dict[str, Any]) -> bool:
        """arXivプレプリントの判定"""
        return True  # arXivは全てプレプリント論文
    
    def parse_article_details(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """arXiv記事の詳細解析"""
        url = article.get('link', '')
        if not url:
            return article
        
        # arXiv URLをabs形式に変換
        if '/abs/' not in url:
            arxiv_id = re.search(r'(\d{4}\.\d{4,5})', url)
            if arxiv_id:
                url = f"https://arxiv.org/abs/{arxiv_id.group(1)}"
        
        self.debug_print(f"Parsing arXiv article: {url}")
        
        soup = self.safe_request(url)
        if not soup:
            return article
        
        # Abstract抽出
        abstract = self._extract_arxiv_abstract(soup)
        if abstract:
            article['abstract'] = abstract
        
        # 著者情報抽出
        authors = self._extract_arxiv_authors(soup)
        if authors:
            article['authors'] = authors
        
        # カテゴリ抽出
        categories = self._extract_arxiv_categories(soup)
        if categories:
            article['keywords'] = categories
        
        return article
    
    def _extract_arxiv_abstract(self, soup: BeautifulSoup) -> str:
        """arXivのアブストラクト抽出"""
        abstract_elem = soup.find('blockquote', class_='abstract')
        if abstract_elem:
            # "Abstract:"テキストを除去
            text = abstract_elem.get_text(strip=True)
            text = re.sub(r'^Abstract:\s*', '', text)
            return text
        return ""
    
    def _extract_arxiv_authors(self, soup: BeautifulSoup) -> List[str]:
        """arXiv著者情報抽出"""
        authors = []
        authors_elem = soup.find('div', class_='authors')
        if authors_elem:
            author_links = authors_elem.find_all('a')
            for link in author_links:
                name = link.get_text(strip=True)
                if name and name not in authors:
                    authors.append(name)
        return authors
    
    def _extract_arxiv_categories(self, soup: BeautifulSoup) -> List[str]:
        """arXivカテゴリ抽出"""
        categories = []
        subjects_elem = soup.find('td', class_='tablecell subjects')
        if subjects_elem:
            for span in subjects_elem.find_all('span', class_='primary-subject'):
                category = span.get_text(strip=True)
                if category:
                    categories.append(category)
        return categories

class GenericParser(BaseJournalParser):
    """汎用RSSパーサー"""
    
    def parse_article_details(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """RSSフィードの情報をそのまま使用"""
        self.debug_print(f"Using generic parser for {article.get('title', 'Unknown')}")
        
        # RSSフィードから取得済みの情報を保持
        if not article.get('abstract') and article.get('summary'):
            article['abstract'] = article['summary']
        
        # 著者情報の整理
        if not article.get('authors'):
            article['authors'] = []
        
        return article
    
    def is_research_article(self, article: Dict[str, Any]) -> bool:
        """汎用パーサーでは全てを記事として扱う"""
        return True

class JournalParserFactory:
    """パーサーファクトリ"""
    
    _parsers = {
        'nature': NatureParser,
        'science': ScienceParser,
        'cell': CellParser,
        'arxiv': ArxivParser,
        'pnas': NatureParser,  # PNASはNatureパーサーを流用
        'nejm': ScienceParser,  # NEJMはScienceパーサーを流用
        'plos': CellParser,  # PLoSはCellパーサーを流用
        'oup': NatureParser,  # Oxford University PressはNatureパーサーを流用
        'generic': GenericParser,
        'default': GenericParser
    }
    
    @classmethod
    def get_parser(cls, parser_type: str, debug: bool = False) -> BaseJournalParser:
        """指定されたタイプのパーサーを取得"""
        parser_class = cls._parsers.get(parser_type, cls._parsers['default'])
        return parser_class(debug=debug)
    
    @classmethod
    def register_parser(cls, parser_type: str, parser_class):
        """新しいパーサーを登録"""
        cls._parsers[parser_type] = parser_class