#!/usr/bin/env python3
import os
import json
import requests
from typing import Dict, Any, Optional
from datetime import datetime

class FeedbackHandler:
    """Slackからのフィードバックを受信してGitHub Issuesに記録するハンドラー"""
    
    def __init__(self):
        self.github_token = os.environ.get('GITHUB_TOKEN')
        self.github_repo = os.environ.get('GITHUB_REPO', 'dakesan/rss_ai_reporter')
        self.slack_signing_secret = os.environ.get('SLACK_SIGNING_SECRET')
        
        if not self.github_token:
            print("WARNING: GITHUB_TOKEN not set. Feedback will be logged locally only.")
        
    def process_slack_feedback(self, payload: Dict[str, Any]) -> bool:
        """Slackのインタラクティブコンポーネントからのペイロードを処理"""
        try:
            # Slackペイロードからフィードバック情報を抽出
            feedback_data = self._extract_feedback_from_payload(payload)
            if not feedback_data:
                print("Invalid feedback payload received")
                return False
            
            print(f"Processing feedback: {feedback_data['feedback']} for article: {feedback_data['article']['title'][:50]}...")
            
            # ローカルログに記録
            self._log_feedback_locally(feedback_data)
            
            # GitHub Issueに記録（トークンがある場合）
            if self.github_token:
                issue_url = self._create_github_issue(feedback_data)
                if issue_url:
                    print(f"Feedback recorded in GitHub Issue: {issue_url}")
                    return True
                else:
                    print("Failed to create GitHub Issue, but feedback logged locally")
                    return False
            else:
                print("Feedback logged locally (GitHub token not available)")
                return True
                
        except Exception as e:
            print(f"Error processing feedback: {str(e)}")
            return False
    
    def _extract_feedback_from_payload(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Slackペイロードからフィードバック情報を抽出"""
        try:
            # Slack Interactive Components payloadの構造を解析
            if 'actions' not in payload or not payload['actions']:
                return None
                
            action = payload['actions'][0]
            action_id = action.get('action_id', '')
            button_value = action.get('value', '')
            
            # ボタンのvalueからフィードバックデータを取得
            if not button_value:
                return None
                
            feedback_info = json.loads(button_value)
            
            # ユーザー情報とチャンネル情報を追加
            user_info = payload.get('user', {})
            channel_info = payload.get('channel', {})
            
            feedback_data = {
                'feedback': feedback_info.get('feedback'),
                'article': feedback_info.get('article'),
                'user': {
                    'id': user_info.get('id'),
                    'name': user_info.get('name', user_info.get('username', 'unknown'))
                },
                'channel': {
                    'id': channel_info.get('id'),
                    'name': channel_info.get('name', 'unknown')
                },
                'timestamp': datetime.now().isoformat(),
                'action_id': action_id
            }
            
            return feedback_data
            
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error parsing feedback payload: {str(e)}")
            return None
    
    def _log_feedback_locally(self, feedback_data: Dict[str, Any]):
        """フィードバックをローカルファイルに記録"""
        log_file = "data/feedback_log.jsonl"
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(feedback_data, ensure_ascii=False) + '\n')
            print(f"Feedback logged locally to {log_file}")
        except Exception as e:
            print(f"Error logging feedback locally: {str(e)}")
    
    def _create_github_issue(self, feedback_data: Dict[str, Any]) -> Optional[str]:
        """GitHub Issueを作成してフィードバックを記録"""
        try:
            article = feedback_data['article']
            feedback = feedback_data['feedback']
            user = feedback_data['user']
            timestamp = feedback_data['timestamp']
            
            # Issueのタイトルと本文を作成
            title = f"Feedback: {feedback} - {article['title'][:80]}"
            
            body = f"""## フィードバック情報

**記事タイトル**: {article['title']}
**ジャーナル**: {article.get('journal', 'Unknown')}
**フィードバック**: {'👍 興味あり' if feedback == 'interested' else '👎 興味なし'}
**ユーザー**: {user['name']} (ID: {user['id']})
**日時**: {timestamp}

### 記事詳細
- **ID**: {article['id']}
- **著者**: {', '.join(article.get('authors', []))}

### フィードバック分析用データ
```json
{json.dumps(feedback_data, indent=2, ensure_ascii=False)}
```

---
*This issue was automatically created by the RSS AI Reporter feedback system.*
"""
            
            # GitHub API でIssueを作成
            url = f"https://api.github.com/repos/{self.github_repo}/issues"
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json',
                'Content-Type': 'application/json'
            }
            
            data = {
                'title': title,
                'body': body,
                'labels': ['feedback', f'feedback-{feedback}']
            }
            
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 201:
                issue_data = response.json()
                return issue_data['html_url']
            else:
                print(f"GitHub API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Error creating GitHub issue: {str(e)}")
            return None
    
    def get_feedback_summary(self, days: int = 7) -> Dict[str, Any]:
        """過去N日間のフィードバック統計を取得"""
        log_file = "data/feedback_log.jsonl"
        
        if not os.path.exists(log_file):
            return {'total': 0, 'interested': 0, 'not_interested': 0, 'articles': []}
        
        from_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        from_date = from_date.replace(day=from_date.day - days)
        
        summary = {
            'total': 0,
            'interested': 0,
            'not_interested': 0,
            'articles': [],
            'keywords': {}
        }
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        feedback_data = json.loads(line.strip())
                        feedback_time = datetime.fromisoformat(feedback_data['timestamp'])
                        
                        if feedback_time >= from_date:
                            summary['total'] += 1
                            
                            if feedback_data['feedback'] == 'interested':
                                summary['interested'] += 1
                            else:
                                summary['not_interested'] += 1
                            
                            # 記事情報を追加
                            article_info = {
                                'title': feedback_data['article']['title'],
                                'journal': feedback_data['article'].get('journal', ''),
                                'feedback': feedback_data['feedback'],
                                'timestamp': feedback_data['timestamp']
                            }
                            summary['articles'].append(article_info)
                            
                    except (json.JSONDecodeError, KeyError):
                        continue
                        
        except Exception as e:
            print(f"Error reading feedback log: {str(e)}")
        
        return summary

if __name__ == "__main__":
    # テスト用
    handler = FeedbackHandler()
    
    # サンプルフィードバック統計を表示
    summary = handler.get_feedback_summary(days=30)
    print("Feedback Summary (last 30 days):")
    print(json.dumps(summary, indent=2, ensure_ascii=False))