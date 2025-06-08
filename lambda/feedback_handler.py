#!/usr/bin/env python3
"""
AWS Lambda用フィードバックハンドラー
Slack Interactive Components Webhookを受信してGitHub Issuesに記録
"""

import json
import os
import urllib.parse
import hmac
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime
import boto3
import requests

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda関数のメインハンドラー
    API GatewayからのSlack Webhookイベントを処理
    """
    
    try:
        print(f"Received event: {json.dumps(event, default=str)}")
        
        # HTTPメソッドとパスを確認
        http_method = event.get('httpMethod', 'POST')
        path = event.get('path', '/')
        
        # ルーティング
        if http_method == 'GET' and path == '/health':
            return handle_health_check()
        elif http_method == 'GET' and path == '/slack/feedback/summary':
            return handle_feedback_summary(event)
        elif http_method == 'POST' and path == '/slack/feedback':
            return handle_slack_feedback(event)
        elif http_method == 'GET' and path == '/':
            return handle_root()
        else:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Not found'})
            }
            
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error'})
        }

def handle_health_check() -> Dict[str, Any]:
    """ヘルスチェックエンドポイント"""
    github_token = os.environ.get('GITHUB_TOKEN')
    slack_secret = os.environ.get('SLACK_SIGNING_SECRET')
    
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'status': 'ok',
            'service': 'RSS AI Reporter Feedback Lambda',
            'github_token': 'configured' if github_token else 'not_configured',
            'slack_secret': 'configured' if slack_secret else 'not_configured',
            'timestamp': datetime.now().isoformat()
        })
    }

def handle_root() -> Dict[str, Any]:
    """ルートエンドポイント"""
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'service': 'RSS AI Reporter Feedback Lambda',
            'endpoints': {
                '/slack/feedback': 'POST - Slack Interactive Components webhook',
                '/slack/feedback/summary': 'GET - Feedback statistics',
                '/health': 'GET - Health check'
            }
        })
    }

def handle_feedback_summary(event: Dict[str, Any]) -> Dict[str, Any]:
    """フィードバック統計の取得"""
    try:
        # クエリパラメータから日数を取得
        query_params = event.get('queryStringParameters') or {}
        days = int(query_params.get('days', '7'))
        
        # S3からフィードバックログを取得して統計を計算
        summary = get_feedback_summary_from_s3(days)
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(summary)
        }
        
    except Exception as e:
        print(f"Error in handle_feedback_summary: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }

def handle_slack_feedback(event: Dict[str, Any]) -> Dict[str, Any]:
    """Slackフィードバックボタンの処理"""
    try:
        # リクエストボディとヘッダーを取得
        body = event.get('body', '')
        headers = event.get('headers', {})
        
        # Slack署名検証
        timestamp = headers.get('X-Slack-Request-Timestamp', headers.get('x-slack-request-timestamp', ''))
        signature = headers.get('X-Slack-Signature', headers.get('x-slack-signature', ''))
        
        if not verify_slack_signature(body, timestamp, signature):
            return {
                'statusCode': 401,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Invalid signature'})
            }
        
        # ペイロードを解析
        if event.get('isBase64Encoded'):
            import base64
            body = base64.b64decode(body).decode('utf-8')
        
        # Content-Typeに応じてペイロードを解析
        content_type = headers.get('Content-Type', headers.get('content-type', ''))
        
        if 'application/json' in content_type:
            payload = json.loads(body)
        else:
            # application/x-www-form-urlencodedの場合
            parsed_body = urllib.parse.parse_qs(body)
            payload_str = parsed_body.get('payload', [''])[0]
            if not payload_str:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'No payload found'})
                }
            payload = json.loads(payload_str)
        
        print(f"Processing feedback payload: {payload.get('type', 'unknown')}")
        
        # フィードバックを処理
        success = process_slack_feedback(payload)
        
        if success:
            # Slackへの応答メッセージを作成
            response_message = create_response_message(payload)
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(response_message)
            }
        else:
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Failed to process feedback'})
            }
            
    except Exception as e:
        print(f"Error in handle_slack_feedback: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error'})
        }

def verify_slack_signature(request_body: str, timestamp: str, signature: str) -> bool:
    """Slackからのリクエストの署名を検証"""
    signing_secret = os.environ.get('SLACK_SIGNING_SECRET')
    if not signing_secret:
        print("WARNING: SLACK_SIGNING_SECRET not set, skipping signature verification")
        return True
    
    # Slackの署名検証
    sig_basestring = f"v0:{timestamp}:{request_body}"
    my_signature = 'v0=' + hmac.new(
        signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(my_signature, signature)

def process_slack_feedback(payload: Dict[str, Any]) -> bool:
    """Slackフィードバックを処理してS3とGitHub Issuesに記録"""
    try:
        # フィードバック情報を抽出
        feedback_data = extract_feedback_from_payload(payload)
        if not feedback_data:
            print("Invalid feedback payload received")
            return False
        
        print(f"Processing feedback: {feedback_data['feedback']} for article: {feedback_data['article']['title'][:50]}...")
        
        # S3にログを記録
        s3_success = log_feedback_to_s3(feedback_data)
        
        # GitHub Issueに記録（トークンがある場合）
        github_token = os.environ.get('GITHUB_TOKEN')
        if github_token:
            github_success = create_github_issue(feedback_data)
            if github_success:
                print(f"Feedback recorded in GitHub Issue")
            else:
                print("Failed to create GitHub Issue, but feedback logged to S3")
        else:
            print("Feedback logged to S3 (GitHub token not available)")
        
        return s3_success
        
    except Exception as e:
        print(f"Error processing feedback: {str(e)}")
        return False

def extract_feedback_from_payload(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Slackペイロードからフィードバック情報を抽出"""
    try:
        if 'actions' not in payload or not payload['actions']:
            return None
            
        action = payload['actions'][0]
        button_value = action.get('value', '')
        
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
            'action_id': action.get('action_id')
        }
        
        return feedback_data
        
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error parsing feedback payload: {str(e)}")
        return None

def log_feedback_to_s3(feedback_data: Dict[str, Any]) -> bool:
    """フィードバックをS3に記録"""
    try:
        s3_bucket = os.environ.get('S3_BUCKET_NAME')
        if not s3_bucket:
            print("S3_BUCKET_NAME not configured, skipping S3 logging")
            return True
        
        s3_client = boto3.client('s3')
        
        # S3キーを日付ベースで作成
        date_str = datetime.now().strftime('%Y/%m/%d')
        timestamp = datetime.now().strftime('%H%M%S%f')
        s3_key = f"feedback-logs/{date_str}/{timestamp}.json"
        
        # S3にアップロード
        s3_client.put_object(
            Bucket=s3_bucket,
            Key=s3_key,
            Body=json.dumps(feedback_data, ensure_ascii=False),
            ContentType='application/json'
        )
        
        print(f"Feedback logged to S3: s3://{s3_bucket}/{s3_key}")
        return True
        
    except Exception as e:
        print(f"Error logging to S3: {str(e)}")
        return False

def create_github_issue(feedback_data: Dict[str, Any]) -> bool:
    """GitHub Issueを作成してフィードバックを記録"""
    try:
        github_token = os.environ.get('GITHUB_TOKEN')
        github_repo = os.environ.get('GITHUB_REPO', 'dakesan/rss_ai_reporter')
        
        if not github_token:
            return False
        
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
*This issue was automatically created by the RSS AI Reporter Lambda feedback system.*
"""
        
        # GitHub API でIssueを作成
        url = f"https://api.github.com/repos/{github_repo}/issues"
        headers = {
            'Authorization': f'token {github_token}',
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
            print(f"GitHub Issue created: {issue_data['html_url']}")
            return True
        else:
            print(f"GitHub API error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"Error creating GitHub issue: {str(e)}")
        return False

def create_response_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    """フィードバック受信後のSlack応答メッセージを作成"""
    try:
        action = payload['actions'][0]
        button_value = json.loads(action['value'])
        feedback = button_value['feedback']
        article_title = button_value['article']['title']
        user_name = payload['user'].get('name', payload['user'].get('username', 'ユーザー'))
        
        if feedback == 'interested':
            emoji = '👍'
            message = 'フィードバックありがとうございます！興味ありとして記録しました。'
        else:
            emoji = '👎'
            message = 'フィードバックありがとうございます！興味なしとして記録しました。'
        
        return {
            "response_type": "ephemeral",
            "text": f"{emoji} {message}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{emoji} *{user_name}さん、フィードバックありがとうございます！*\n\n_{article_title[:100]}..._\n\n{message}\n\n継続学習システムでフィルター改善に活用させていただきます。"
                    }
                }
            ]
        }
        
    except Exception as e:
        print(f"Error creating response message: {str(e)}")
        return {
            "response_type": "ephemeral",
            "text": "フィードバックを受信しました。ありがとうございます！"
        }

def get_feedback_summary_from_s3(days: int = 7) -> Dict[str, Any]:
    """S3からフィードバック統計を取得"""
    try:
        s3_bucket = os.environ.get('S3_BUCKET_NAME')
        if not s3_bucket:
            return {'total': 0, 'interested': 0, 'not_interested': 0, 'articles': []}
        
        s3_client = boto3.client('s3')
        
        # 過去N日間のプレフィックスを生成
        from_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        date_prefixes = []
        for i in range(days):
            date = from_date.replace(day=from_date.day - i)
            date_prefixes.append(f"feedback-logs/{date.strftime('%Y/%m/%d')}/")
        
        summary = {
            'total': 0,
            'interested': 0,
            'not_interested': 0,
            'articles': []
        }
        
        # 各日付のフィードバックを取得
        for prefix in date_prefixes:
            try:
                response = s3_client.list_objects_v2(Bucket=s3_bucket, Prefix=prefix)
                
                for obj in response.get('Contents', []):
                    try:
                        # S3からオブジェクトを取得
                        content = s3_client.get_object(Bucket=s3_bucket, Key=obj['Key'])
                        feedback_data = json.loads(content['Body'].read().decode('utf-8'))
                        
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
                        
                    except Exception as obj_e:
                        print(f"Error processing S3 object {obj['Key']}: {str(obj_e)}")
                        continue
                        
            except Exception as prefix_e:
                print(f"Error processing prefix {prefix}: {str(prefix_e)}")
                continue
        
        return summary
        
    except Exception as e:
        print(f"Error getting feedback summary from S3: {str(e)}")
        return {'total': 0, 'interested': 0, 'not_interested': 0, 'articles': []}