#!/usr/bin/env python3
"""
新ジャーナル追加時のテストスイート
特にGemini処理互換性の確認が重要
"""
import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
import json

# パスを追加してsrcモジュールをインポート
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from content_fetcher import ContentFetcher
from summarizer import Summarizer
from rss_fetcher import RSSFetcher
from queue_manager import QueueManager

class TestNewJournalCompatibility(unittest.TestCase):
    """新ジャーナルのシステム互換性テスト"""
    
    def setUp(self):
        self.content_fetcher = ContentFetcher(debug_mode=True)
        self.queue_manager = QueueManager()
        
    def test_cell_journal_parsing(self):
        """Cell誌の記事解析テスト"""
        sample_article = {
            'id': 'test-cell-001',
            'journal': 'Cell',
            'title': 'Cellular reprogramming through metabolic regulation',
            'link': 'https://www.cell.com/cell/fulltext/test-article',
            'published': '2025-06-08',
            'summary': 'Short summary from RSS',
            'authors': [],
            'doi': '10.1016/j.cell.2025.test'
        }
        
        # Mock HTML response
        mock_html = """
        <html>
            <div class="summary-content">
                <p>This study reveals novel mechanisms of cellular reprogramming through metabolic regulation, 
                   providing insights into stem cell biology and regenerative medicine applications.</p>
            </div>
            <div class="author-group">
                <span class="author">Dr. Jane Smith</span>
                <span class="author">Dr. John Doe</span>
            </div>
        </html>
        """
        
        with patch('requests.Session.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = mock_html.encode('utf-8')
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            # パーサーテスト
            result = self.content_fetcher.fetch_article_details(sample_article)
            
            # 必須フィールドの確認
            self.assertIn('abstract', result)
            self.assertIn('authors', result)
            self.assertTrue(len(result['abstract']) > 50)
            self.assertTrue(len(result['authors']) >= 2)
            
    def test_nejm_journal_parsing(self):
        """NEJM誌の記事解析テスト"""
        sample_article = {
            'id': 'test-nejm-001',
            'journal': 'NEJM',
            'title': 'Clinical trial results for novel cancer therapy',
            'link': 'https://www.nejm.org/doi/full/test-article',
            'published': '2025-06-08',
            'summary': 'Short summary from RSS',
            'authors': [],
            'doi': '10.1056/NEJMtest2025'
        }
        
        # Mock HTML response  
        mock_html = """
        <html>
            <div class="o-article-body__section--first">
                <p>A randomized controlled trial demonstrates significant efficacy of the novel therapeutic approach 
                   in treating advanced stage cancer patients, with minimal adverse effects reported.</p>
            </div>
            <div class="m-author-list">
                <div class="m-author-list__item">Dr. Alice Johnson</div>
                <div class="m-author-list__item">Dr. Bob Wilson</div>
            </div>
        </html>
        """
        
        with patch('requests.Session.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = mock_html.encode('utf-8')
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            result = self.content_fetcher.fetch_article_details(sample_article)
            
            # 必須フィールドの確認
            self.assertIn('abstract', result)
            self.assertIn('authors', result)
            self.assertTrue(len(result['abstract']) > 50)
            self.assertTrue(len(result['authors']) >= 2)
    
    def test_arxiv_journal_parsing(self):
        """arXiv記事の解析テスト"""
        sample_article = {
            'id': 'test-arxiv-001',
            'journal': 'arXiv_CS',
            'title': 'Novel machine learning architecture for quantum computing',
            'link': 'https://arxiv.org/abs/2506.12345',
            'published': '2025-06-08',
            'summary': 'Short summary from RSS',
            'authors': [],
            'doi': ''
        }
        
        # Mock HTML response
        mock_html = """
        <html>
            <blockquote class="abstract">
                Abstract: We present a novel machine learning architecture specifically designed for quantum 
                computing applications, demonstrating superior performance in quantum state classification tasks.
            </blockquote>
            <div class="authors">
                <a href="#">Dr. Quantum Smith</a>, 
                <a href="#">Dr. ML Johnson</a>
            </div>
            <td class="tablecell subjects">
                <span class="primary-subject">Computer Science - Machine Learning</span>
            </td>
        </html>
        """
        
        with patch('requests.Session.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = mock_html.encode('utf-8')
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            result = self.content_fetcher.fetch_article_details(sample_article)
            
            # 必須フィールドの確認
            self.assertIn('abstract', result)
            self.assertIn('authors', result)
            self.assertIn('keywords', result)
            self.assertTrue(len(result['abstract']) > 50)
            self.assertFalse(result['abstract'].startswith('Abstract:'))  # プレフィックス除去確認

class TestGeminiCompatibility(unittest.TestCase):
    """Gemini API処理互換性テスト"""
    
    def setUp(self):
        # Gemini APIキーが設定されていない場合はスキップ
        if not os.environ.get('GEMINI_API_KEY'):
            self.skipTest("GEMINI_API_KEY not set")
        
        self.summarizer = Summarizer(debug_mode=True)
    
    def test_cell_article_gemini_processing(self):
        """Cell記事のGemini処理テスト"""
        sample_article = {
            'id': 'test-cell-gemini',
            'journal': 'Cell',
            'title': 'CRISPR-mediated genome editing in primary human cells',
            'abstract': 'We developed an improved CRISPR-Cas9 system for efficient genome editing in primary human cells. The method shows 95% editing efficiency with minimal off-target effects, opening new possibilities for therapeutic applications in genetic diseases.',
            'authors': ['Dr. Gene Editor', 'Dr. Cell Biologist'],
            'link': 'https://www.cell.com/test',
            'published': '2025-06-08'
        }
        
        # Gemini処理テスト
        try:
            result = self.summarizer.batch_summarize([sample_article])
            
            # 結果検証
            self.assertEqual(len(result), 1)
            processed_article = result[0]
            
            # 必須フィールドの確認
            self.assertIn('summary_ja', processed_article)
            self.assertTrue(len(processed_article['summary_ja']) > 0)
            self.assertTrue(len(processed_article['summary_ja']) <= 300)
            
            # 日本語文字が含まれているか確認
            import re
            has_japanese = bool(re.search(r'[ひらがなカタカナ漢字]', processed_article['summary_ja']))
            self.assertTrue(has_japanese, "Summary should contain Japanese characters")
            
        except Exception as e:
            self.fail(f"Gemini processing failed for Cell article: {e}")
    
    def test_arxiv_article_gemini_processing(self):
        """arXiv記事のGemini処理テスト"""
        sample_article = {
            'id': 'test-arxiv-gemini',
            'journal': 'arXiv_CS',
            'title': 'Transformer Architecture for Quantum Machine Learning',
            'abstract': 'This paper presents a novel transformer-based architecture specifically designed for quantum machine learning tasks. We demonstrate superior performance on quantum state classification and quantum circuit optimization problems compared to classical approaches.',
            'authors': ['Dr. Quantum AI', 'Dr. ML Researcher'],
            'link': 'https://arxiv.org/abs/test',
            'published': '2025-06-08',
            'keywords': ['Machine Learning', 'Quantum Computing']
        }
        
        try:
            result = self.summarizer.batch_summarize([sample_article])
            
            # 結果検証
            self.assertEqual(len(result), 1)
            processed_article = result[0]
            
            # 必須フィールドの確認
            self.assertIn('summary_ja', processed_article)
            self.assertTrue(len(processed_article['summary_ja']) > 0)
            
            # キーワードが保持されているか確認
            self.assertIn('keywords', processed_article)
            
        except Exception as e:
            self.fail(f"Gemini processing failed for arXiv article: {e}")

class TestQueueManagerCompatibility(unittest.TestCase):
    """QueueManagerの新ジャーナル対応テスト"""
    
    def setUp(self):
        self.queue_manager = QueueManager("test_queue.json")
        # テスト後のクリーンアップ
        if os.path.exists("test_queue.json"):
            os.remove("test_queue.json")
    
    def tearDown(self):
        if os.path.exists("test_queue.json"):
            os.remove("test_queue.json")
    
    def test_priority_calculation_new_journals(self):
        """新ジャーナルの優先度計算テスト"""
        test_articles = [
            {
                'id': 'cell-001',
                'journal': 'Cell',
                'title': 'CRISPR breakthrough in cancer therapy',
                'abstract': 'Revolutionary CRISPR technique...',
                'link': 'https://www.cell.com/test'
            },
            {
                'id': 'nejm-001', 
                'journal': 'NEJM',
                'title': 'Clinical trial results for COVID vaccine',
                'abstract': 'Large-scale clinical trial...',
                'link': 'https://www.nejm.org/test'
            },
            {
                'id': 'arxiv-001',
                'journal': 'arXiv_CS',
                'title': 'Machine learning advances in quantum computing',
                'abstract': 'Novel ML architecture...',
                'link': 'https://arxiv.org/abs/test'
            }
        ]
        
        # 優先度計算テスト
        for article in test_articles:
            priority = self.queue_manager.calculate_priority(article)
            
            # Cell、NEJMは高優先度ジャーナル
            if article['journal'] in ['Cell', 'NEJM']:
                self.assertEqual(priority.name, 'HIGH')
            # arXivは通常優先度
            elif article['journal'].startswith('arXiv'):
                self.assertIn(priority.name, ['HIGH', 'NORMAL'])  # キーワード次第
    
    def test_batch_processing_mixed_journals(self):
        """複数ジャーナル混在時のバッチ処理テスト"""
        test_articles = [
            {'id': 'nature-001', 'journal': 'Nature', 'title': 'Nature article', 'added_at': '2025-06-08T10:00:00'},
            {'id': 'cell-001', 'journal': 'Cell', 'title': 'Cell article', 'added_at': '2025-06-08T10:01:00'},
            {'id': 'arxiv-001', 'journal': 'arXiv_CS', 'title': 'arXiv article', 'added_at': '2025-06-08T10:02:00'},
            {'id': 'plos-001', 'journal': 'PLoS_ONE', 'title': 'PLoS article', 'added_at': '2025-06-08T10:03:00'}
        ]
        
        # 記事をキューに追加
        added_count = self.queue_manager.add_articles(test_articles)
        self.assertEqual(added_count, 4)
        
        # バッチ取得テスト
        batch = self.queue_manager.get_batch(batch_size=2)
        self.assertEqual(len(batch), 2)
        
        # 優先度順にソートされているか確認
        priorities = [article.get('priority', 3) for article in batch]
        self.assertEqual(priorities, sorted(priorities))

class TestSystemIntegration(unittest.TestCase):
    """システム統合テスト"""
    
    def test_feeds_config_validation(self):
        """feeds_config.jsonの検証"""
        config_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'feeds_config.json')
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 必須フィールドの確認
        self.assertIn('feeds', config)
        self.assertIn('global_settings', config)
        self.assertIn('parser_configs', config)
        
        # 新ジャーナルが含まれているか確認
        feeds = config['feeds']
        expected_journals = ['Nature', 'Science', 'Cell', 'NEJM', 'PNAS', 'arXiv_CS', 'arXiv_QB', 'PLoS_ONE']
        
        for journal in expected_journals:
            self.assertIn(journal, feeds)
            
            # 各フィードの必須フィールド確認
            feed_config = feeds[journal]
            required_fields = ['url', 'enabled', 'priority', 'parser_type', 'description']
            for field in required_fields:
                self.assertIn(field, feed_config)
    
    def test_rss_fetcher_new_journals(self):
        """RSSFetcher の新ジャーナル対応テスト"""
        rss_fetcher = RSSFetcher()
        
        # 設定読み込み確認
        enabled_feeds = rss_fetcher.get_enabled_feeds()
        
        # 有効な新ジャーナルが含まれているか確認
        expected_enabled = ['Nature', 'Science', 'Cell', 'NEJM', 'PNAS', 'arXiv_CS', 'arXiv_QB', 'PLoS_ONE']
        
        for journal in expected_enabled:
            if journal in enabled_feeds:
                feed_config = enabled_feeds[journal]
                self.assertTrue(feed_config.get('enabled', False))
                self.assertIn('parser_type', feed_config)

def run_journal_tests(journal_name: str = None):
    """特定ジャーナルのテストを実行"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    if journal_name:
        # 特定ジャーナルのテストのみ実行
        test_methods = [
            f'test_{journal_name.lower()}_journal_parsing',
            f'test_{journal_name.lower()}_article_gemini_processing'
        ]
        for method in test_methods:
            try:
                if hasattr(TestNewJournalCompatibility, method):
                    suite.addTest(TestNewJournalCompatibility(method))
                if hasattr(TestGeminiCompatibility, method):
                    suite.addTest(TestGeminiCompatibility(method))
            except AttributeError:
                pass
    else:
        # 全テスト実行
        suite.addTests(loader.loadTestsFromTestCase(TestNewJournalCompatibility))
        suite.addTests(loader.loadTestsFromTestCase(TestGeminiCompatibility))
        suite.addTests(loader.loadTestsFromTestCase(TestQueueManagerCompatibility))
        suite.addTests(loader.loadTestsFromTestCase(TestSystemIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='新ジャーナル対応テスト')
    parser.add_argument('--journal', choices=['cell', 'nejm', 'pnas', 'arxiv', 'plos'], 
                       help='特定ジャーナルのテストのみ実行')
    parser.add_argument('--gemini-only', action='store_true', 
                       help='Gemini互換性テストのみ実行')
    
    args = parser.parse_args()
    
    if args.gemini_only:
        suite = unittest.TestLoader().loadTestsFromTestCase(TestGeminiCompatibility)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
    else:
        success = run_journal_tests(args.journal)
        sys.exit(0 if success else 1)