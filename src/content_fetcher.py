import requests
from bs4 import BeautifulSoup
import time
from typing import Dict, Any, Optional
from urllib.parse import urlparse

class ContentFetcher:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; RSS_Paper_Summarizer/1.0; +https://github.com/your-repo)'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def fetch_article_details(self, article: Dict[str, Any]) -> Dict[str, Any]:
        url = article.get('link', '')
        journal = article.get('journal', '')
        
        if not url:
            return article
        
        try:
            # robots.txtを尊重するため、1秒間隔を空ける
            time.sleep(1)
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # ジャーナルごとに異なる構造に対応
            if journal == "Nature":
                article.update(self._parse_nature_article(soup, article))
            elif journal == "Science":
                article.update(self._parse_science_article(soup, article))
            else:
                article.update(self._parse_generic_article(soup, article))
                
        except Exception as e:
            print(f"Error fetching article details from {url}: {str(e)}")
            
        return article
    
    def _parse_nature_article(self, soup: BeautifulSoup, article: Dict[str, Any]) -> Dict[str, Any]:
        details = {}
        
        # アブストラクトの取得
        abstract_elem = soup.find('div', {'id': 'Abs1-content'}) or \
                       soup.find('div', {'class': 'c-article-section__content'}) or \
                       soup.find('section', {'aria-labelledby': 'Abs1'})
        
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
        
        # アブストラクトの取得
        abstract_elem = soup.find('div', {'class': 'section abstract'}) or \
                       soup.find('section', {'id': 'abstract'}) or \
                       soup.find('div', {'class': 'abstract-content'})
        
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
        
        for pattern in abstract_patterns:
            elem = soup.find(**pattern)
            if elem:
                if pattern['name'] == 'meta':
                    details['abstract'] = elem.get('content', '')
                else:
                    details['abstract'] = elem.get_text(strip=True)
                break
        
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