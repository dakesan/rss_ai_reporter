#!/usr/bin/env python3
"""
フィードバック分析エンジン

ユーザーフィードバックを分析し、興味パターンを抽出して
フィルター設定の改善提案を生成する。
"""

import json
import os
import re
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter
import logging

import google.generativeai as genai


class FeedbackAnalyzer:
    """フィードバックデータの AI 分析エンジン"""
    
    def __init__(self, gemini_api_key: str = None, debug: bool = False):
        """
        Args:
            gemini_api_key: Gemini API キー
            debug: デバッグモード
        """
        self.debug = debug
        self.logger = self._setup_logger()
        
        # Gemini API 設定
        api_key = gemini_api_key or os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("Gemini API key is required")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        # パス設定
        self.feedback_log_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'data', 'feedback_log.jsonl'
        )
        self.filter_config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'data', 'filter_config.json'
        )
    
    def _setup_logger(self) -> logging.Logger:
        """ロガーを設定"""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG if self.debug else logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def fetch_feedback_from_issues(self, days: int = 30) -> List[Dict]:
        """
        GitHub Issues APIを使ってフィードバックデータを取得
        
        Args:
            days: 過去何日分のデータを対象とするか
            
        Returns:
            フィードバックデータのリスト
        """
        feedback_data = []
        # タイムゾーンaware datetimeで統一
        from datetime import timezone
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        try:
            self.logger.info(f"Fetching feedback issues from GitHub...")
            
            # GitHub CLI でフィードバックラベルの issue を取得
            cmd = [
                'gh', 'issue', 'list', 
                '--label', 'feedback',
                '--state', 'all',
                '--limit', '100',
                '--json', 'number,title,body,createdAt,labels'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            issues = json.loads(result.stdout)
            
            self.logger.info(f"Found {len(issues)} feedback issues")
            
            for issue in issues:
                try:
                    # 日付フィルタリング（タイムゾーン対応）
                    created_at = datetime.fromisoformat(issue['createdAt'].replace('Z', '+00:00'))
                    if created_at < cutoff_date:
                        continue
                    
                    # issue body からJSONデータを抽出
                    body = issue['body']
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', body, re.DOTALL)
                    
                    if not json_match:
                        self.logger.warning(f"No JSON data found in issue #{issue['number']}")
                        continue
                    
                    # JSONデータをパース
                    json_data = json.loads(json_match.group(1))
                    
                    # フィードバックデータ形式に変換
                    feedback_entry = {
                        'feedback': json_data['feedback'],
                        'article': json_data['article'],
                        'user': json_data['user'],
                        'channel': json_data['channel'],
                        'timestamp': json_data['timestamp'],
                        'action_id': json_data['action_id'],
                        'source': 'github_issues',
                        'issue_number': issue['number']
                    }
                    
                    feedback_data.append(feedback_entry)
                    
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    self.logger.warning(f"Issue #{issue['number']} parsing error: {e}")
                    continue
            
            self.logger.info(f"Successfully parsed {len(feedback_data)} feedback entries from GitHub Issues")
            return feedback_data
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"GitHub CLI error: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Error fetching feedback from GitHub Issues: {e}")
            return []
    
    def load_feedback_data(self, days: int = 30) -> List[Dict]:
        """
        フィードバックデータを読み込む（GitHub Issues + ローカルファイル統合）
        
        Args:
            days: 過去何日分のデータを対象とするか
            
        Returns:
            フィードバックデータのリスト
        """
        feedback_data = []
        
        # GitHub Issues からフィードバックデータを取得
        issues_data = self.fetch_feedback_from_issues(days)
        feedback_data.extend(issues_data)
        
        # ローカルファイルからもフィードバックデータを取得（補完用）
        if os.path.exists(self.feedback_log_path):
            from datetime import timezone
            local_cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            try:
                with open(self.feedback_log_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        try:
                            data = json.loads(line.strip())
                            
                            # タイムスタンプ確認（タイムゾーン対応）
                            timestamp_str = data['timestamp']
                            if 'Z' in timestamp_str:
                                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            elif '+' in timestamp_str or '-' in timestamp_str[-6:]:
                                timestamp = datetime.fromisoformat(timestamp_str)
                            else:
                                # タイムゾーン情報がない場合はUTCとして扱う
                                timestamp = datetime.fromisoformat(timestamp_str).replace(tzinfo=timezone.utc)
                            
                            if timestamp >= local_cutoff_date:
                                # GitHub Issues に無い重複データは除外
                                article_id = data['article']['id']
                                if not any(entry['article']['id'] == article_id and 
                                         entry['feedback'] == data['feedback'] 
                                         for entry in issues_data):
                                    data['source'] = 'local_file'
                                    feedback_data.append(data)
                            
                        except (json.JSONDecodeError, KeyError, ValueError) as e:
                            self.logger.warning(f"Line {line_num} parsing error: {e}")
                            continue
                
            except Exception as e:
                self.logger.error(f"Error loading local feedback data: {e}")
        
        self.logger.info(f"Total loaded {len(feedback_data)} feedback entries from last {days} days")
        self.logger.info(f"  - GitHub Issues: {len(issues_data)} entries")
        self.logger.info(f"  - Local file: {len(feedback_data) - len(issues_data)} entries")
        
        return feedback_data
    
    def extract_patterns(self, feedback_data: List[Dict]) -> Dict:
        """
        フィードバックデータから基本的なパターンを抽出
        
        Args:
            feedback_data: フィードバックデータ
            
        Returns:
            抽出されたパターン情報
        """
        patterns = {
            'interested': {'titles': [], 'authors': [], 'journals': []},
            'not_interested': {'titles': [], 'authors': [], 'journals': []},
            'statistics': {
                'total_feedback': len(feedback_data),
                'interested_count': 0,
                'not_interested_count': 0
            }
        }
        
        for entry in feedback_data:
            feedback_type = entry['feedback']
            article = entry['article']
            
            # 統計情報
            if feedback_type == 'interested':
                patterns['statistics']['interested_count'] += 1
            else:
                patterns['statistics']['not_interested_count'] += 1
            
            # パターン抽出
            patterns[feedback_type]['titles'].append(article['title'])
            patterns[feedback_type]['authors'].extend(article.get('authors', []))
            patterns[feedback_type]['journals'].append(article.get('journal', ''))
        
        # 重複削除と集計
        for feedback_type in ['interested', 'not_interested']:
            patterns[feedback_type]['author_counts'] = Counter(
                patterns[feedback_type]['authors']
            )
            patterns[feedback_type]['journal_counts'] = Counter(
                patterns[feedback_type]['journals']
            )
        
        self.logger.info(f"Extracted patterns: {patterns['statistics']}")
        return patterns
    
    def analyze_with_gemini(self, patterns: Dict) -> Dict:
        """
        Gemini API を使用してパターンを分析
        
        Args:
            patterns: 抽出されたパターン
            
        Returns:
            AI 分析結果
        """
        if patterns['statistics']['total_feedback'] < 3:
            self.logger.warning("Insufficient feedback data for AI analysis")
            return {'analysis': 'Insufficient data', 'recommendations': []}
        
        # 興味ありタイトルを分析
        interested_titles = patterns['interested']['titles']
        not_interested_titles = patterns['not_interested']['titles']
        
        prompt = f"""
以下のユーザーフィードバックデータを分析し、興味パターンを特定してください：

【興味ありの論文タイトル】
{chr(10).join(f"- {title}" for title in interested_titles)}

【興味なしの論文タイトル】  
{chr(10).join(f"- {title}" for title in not_interested_titles)}

以下の観点で分析し、JSON形式で回答してください：

1. 興味ありパターンの特徴（キーワード、研究分野、手法など）
2. 興味なしパターンの特徴  
3. 新しいキーワード候補（include用）
4. 除外キーワード候補（exclude用）
5. 全体的な傾向

回答形式：
{{
  "interested_patterns": {{
    "keywords": ["キーワード1", "キーワード2"],
    "fields": ["研究分野1", "研究分野2"],
    "characteristics": "特徴の説明"
  }},
  "not_interested_patterns": {{
    "keywords": ["キーワード1", "キーワード2"], 
    "characteristics": "特徴の説明"
  }},
  "recommendations": {{
    "new_include_keywords": ["推奨キーワード1", "推奨キーワード2"],
    "new_exclude_keywords": ["除外キーワード1", "除外キーワード2"],
    "reasoning": "推奨理由"
  }},
  "summary": "全体分析のまとめ"
}}
"""
        
        try:
            self.logger.info("Sending analysis request to Gemini...")
            response = self.model.generate_content(prompt)
            
            # JSON抽出
            response_text = response.text
            if self.debug:
                self.logger.debug(f"Gemini response: {response_text}")
            
            # JSON部分を抽出
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                analysis_result = json.loads(json_str)
                self.logger.info("Gemini analysis completed successfully")
                return analysis_result
            else:
                self.logger.error("No JSON found in Gemini response")
                return {'analysis': 'Parse error', 'recommendations': []}
                
        except Exception as e:
            self.logger.error(f"Gemini analysis error: {e}")
            return {'analysis': f'Error: {e}', 'recommendations': []}
    
    def load_current_filters(self) -> Dict:
        """現在のフィルター設定を読み込む"""
        try:
            with open(self.filter_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.warning("Filter config not found, using defaults")
            return {"include": [], "exclude": []}
        except Exception as e:
            self.logger.error(f"Error loading filter config: {e}")
            return {"include": [], "exclude": []}
    
    def generate_filter_recommendations(self, analysis: Dict) -> Dict:
        """
        分析結果からフィルター更新の推奨事項を生成
        
        Args:
            analysis: AI分析結果
            
        Returns:
            フィルター更新推奨事項
        """
        current_filters = self.load_current_filters()
        recommendations = analysis.get('recommendations', {})
        
        # 新しいキーワード候補
        new_includes = recommendations.get('new_include_keywords', [])
        new_excludes = recommendations.get('new_exclude_keywords', [])
        
        # 重複除去
        current_includes = set(current_filters.get('include', []))
        current_excludes = set(current_filters.get('exclude', []))
        
        suggested_includes = [kw for kw in new_includes if kw not in current_includes]
        suggested_excludes = [kw for kw in new_excludes if kw not in current_excludes]
        
        return {
            'current_filters': current_filters,
            'suggested_additions': {
                'include': suggested_includes,
                'exclude': suggested_excludes
            },
            'updated_filters': {
                'include': list(current_includes) + suggested_includes,
                'exclude': list(current_excludes) + suggested_excludes
            },
            'reasoning': recommendations.get('reasoning', ''),
            'confidence': len(analysis.get('interested_patterns', {}).get('keywords', [])) + 
                        len(analysis.get('not_interested_patterns', {}).get('keywords', []))
        }
    
    def run_analysis(self, days: int = 30, min_feedback: int = 3) -> Dict:
        """
        フィードバック分析を実行
        
        Args:
            days: 分析対象期間（日数）
            min_feedback: 分析に必要な最小フィードバック数
            
        Returns:
            分析結果と推奨事項
        """
        self.logger.info(f"Starting feedback analysis for last {days} days")
        
        # データ読み込み
        feedback_data = self.load_feedback_data(days)
        
        if len(feedback_data) < min_feedback:
            return {
                'status': 'insufficient_data',
                'message': f'Need at least {min_feedback} feedback entries, got {len(feedback_data)}',
                'data_count': len(feedback_data)
            }
        
        # パターン抽出
        patterns = self.extract_patterns(feedback_data)
        
        # AI分析
        ai_analysis = self.analyze_with_gemini(patterns)
        
        # フィルター推奨事項生成
        filter_recommendations = self.generate_filter_recommendations(ai_analysis)
        
        return {
            'status': 'success',
            'data_count': len(feedback_data),
            'analysis_period': f'{days} days',
            'patterns': patterns,
            'ai_analysis': ai_analysis,
            'filter_recommendations': filter_recommendations,
            'timestamp': datetime.now().isoformat()
        }


def main():
    """メイン関数 - CLIテスト用"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Feedback Analysis Engine')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--days', type=int, default=30, help='Analysis period in days')
    parser.add_argument('--min-feedback', type=int, default=3, help='Minimum feedback count')
    
    args = parser.parse_args()
    
    try:
        analyzer = FeedbackAnalyzer(debug=args.debug)
        result = analyzer.run_analysis(days=args.days, min_feedback=args.min_feedback)
        
        print("=" * 60)
        print("📊 FEEDBACK ANALYSIS RESULTS")
        print("=" * 60)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())