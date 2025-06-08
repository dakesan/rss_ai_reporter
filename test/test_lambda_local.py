#!/usr/bin/env python3
"""
AWS Lambda関数のローカルテスト
SAM Local を使わずにLambda関数を直接テスト
"""

import sys
import os
import json
import urllib.parse
from datetime import datetime

# パスを追加してlambdaモジュールをインポート
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from feedback_handler import lambda_handler

def create_api_gateway_event(
    method: str = "POST", 
    path: str = "/slack/feedback", 
    body: str = "",
    headers: dict = None,
    query_params: dict = None
) -> dict:
    """API Gatewayイベントのモックを作成"""
    
    if headers is None:
        headers = {}
    
    if query_params is None:
        query_params = {}
    
    # デフォルトヘッダー
    default_headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Slack-Test/1.0",
        "X-Slack-Request-Timestamp": str(int(datetime.now().timestamp())),
        "X-Slack-Signature": "v0=test_signature"
    }
    
    default_headers.update(headers)
    
    return {
        "httpMethod": method,
        "path": path,
        "pathParameters": None,
        "queryStringParameters": query_params if query_params else None,
        "headers": default_headers,
        "body": body,
        "isBase64Encoded": False,
        "requestContext": {
            "requestId": "test-request-id",
            "stage": "test",
            "resourcePath": path,
            "httpMethod": method,
            "identity": {
                "sourceIp": "127.0.0.1",
                "userAgent": "Slack-Test/1.0"
            }
        }
    }

def create_slack_feedback_payload():
    """テスト用Slackフィードバックペイロードを作成"""
    article_data = {
        "id": "https://www.nature.com/articles/lambda-test-1",
        "title": "Lambda Test: Serverless Machine Learning for Scientific Discovery",
        "journal": "Nature",
        "authors": ["Dr. Lambda Tester", "Dr. Serverless Researcher"],
        "timestamp": datetime.now().isoformat()
    }
    
    payload = {
        "type": "block_actions",
        "user": {
            "id": "U_LAMBDA_TEST",
            "username": "lambda_tester",
            "name": "Lambda Tester"
        },
        "api_app_id": "A_LAMBDA_TEST",
        "token": "lambda_test_token",
        "container": {
            "message_ts": "1691234567.123456"
        },
        "trigger_id": "lambda_test_trigger_id",
        "team": {
            "id": "T_LAMBDA_TEST",
            "domain": "lambda-test-workspace"
        },
        "channel": {
            "id": "C_LAMBDA_TEST",
            "name": "lambda-test-channel"
        },
        "response_url": "https://hooks.slack.com/actions/lambda/test",
        "actions": [
            {
                "action_id": "feedback_interested",
                "block_id": "feedback_block_lambda_test",
                "text": {
                    "type": "plain_text",
                    "text": "👍 興味あり",
                    "emoji": True
                },
                "value": json.dumps({
                    "feedback": "interested",
                    "article": article_data
                }),
                "type": "button",
                "action_ts": "1691234567.789123"
            }
        ]
    }
    
    return payload

def test_health_check():
    """ヘルスチェックエンドポイントのテスト"""
    print("\n🧪 Testing Health Check Endpoint...")
    
    event = create_api_gateway_event("GET", "/health")
    context = {}
    
    try:
        response = lambda_handler(event, context)
        
        if response['statusCode'] == 200:
            data = json.loads(response['body'])
            print(f"   ✅ Health check passed")
            print(f"   Service: {data.get('service')}")
            print(f"   Status: {data.get('status')}")
            print(f"   GitHub Token: {data.get('github_token')}")
            print(f"   Slack Secret: {data.get('slack_secret')}")
            return True
        else:
            print(f"   ❌ Health check failed: {response['statusCode']}")
            print(f"   Response: {response['body']}")
            return False
            
    except Exception as e:
        print(f"   ❌ Health check error: {e}")
        return False

def test_root_endpoint():
    """ルートエンドポイントのテスト"""
    print("\n🧪 Testing Root Endpoint...")
    
    event = create_api_gateway_event("GET", "/")
    context = {}
    
    try:
        response = lambda_handler(event, context)
        
        if response['statusCode'] == 200:
            data = json.loads(response['body'])
            print(f"   ✅ Root endpoint accessible")
            print(f"   Service: {data.get('service')}")
            print(f"   Endpoints: {len(data.get('endpoints', {}))}")
            return True
        else:
            print(f"   ❌ Root endpoint failed: {response['statusCode']}")
            return False
            
    except Exception as e:
        print(f"   ❌ Root endpoint error: {e}")
        return False

def test_feedback_summary():
    """フィードバック統計エンドポイントのテスト"""
    print("\n🧪 Testing Feedback Summary Endpoint...")
    
    event = create_api_gateway_event("GET", "/slack/feedback/summary", query_params={"days": "7"})
    context = {}
    
    try:
        response = lambda_handler(event, context)
        
        if response['statusCode'] == 200:
            data = json.loads(response['body'])
            print(f"   ✅ Feedback summary accessible")
            print(f"   Total feedbacks: {data.get('total', 0)}")
            print(f"   Interested: {data.get('interested', 0)}")
            print(f"   Not interested: {data.get('not_interested', 0)}")
            return True
        else:
            print(f"   ❌ Feedback summary failed: {response['statusCode']}")
            print(f"   Response: {response['body']}")
            return False
            
    except Exception as e:
        print(f"   ❌ Feedback summary error: {e}")
        return False

def test_slack_feedback():
    """Slackフィードバック送信のテスト"""
    print("\n🧪 Testing Slack Feedback Submission...")
    
    # Slackペイロードを作成
    payload = create_slack_feedback_payload()
    payload_str = json.dumps(payload)
    
    # form-dataとして送信（Slackの実際の形式）
    body = urllib.parse.urlencode({"payload": payload_str})
    
    event = create_api_gateway_event(
        "POST", 
        "/slack/feedback",
        body=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    context = {}
    
    try:
        response = lambda_handler(event, context)
        
        if response['statusCode'] == 200:
            data = json.loads(response['body'])
            print(f"   ✅ Feedback submission successful")
            print(f"   Response type: {data.get('response_type')}")
            print(f"   Message: {data.get('text', '')[:100]}...")
            return True
        else:
            print(f"   ❌ Feedback submission failed: {response['statusCode']}")
            print(f"   Response: {response['body']}")
            return False
            
    except Exception as e:
        print(f"   ❌ Feedback submission error: {e}")
        return False

def test_invalid_routes():
    """無効なルートのテスト"""
    print("\n🧪 Testing Invalid Routes...")
    
    test_cases = [
        ("GET", "/invalid/path"),
        ("POST", "/invalid/endpoint"),
        ("PUT", "/slack/feedback"),
        ("DELETE", "/health")
    ]
    
    passed = 0
    for method, path in test_cases:
        try:
            event = create_api_gateway_event(method, path)
            response = lambda_handler(event, {})
            
            if response['statusCode'] == 404:
                print(f"   ✅ {method} {path} correctly returned 404")
                passed += 1
            else:
                print(f"   ❌ {method} {path} returned {response['statusCode']} (expected 404)")
                
        except Exception as e:
            print(f"   ❌ {method} {path} error: {e}")
    
    return passed == len(test_cases)

def main():
    """メイン実行関数"""
    print("🚀 RSS AI Reporter - Lambda Function Local Test")
    print("=" * 60)
    
    # 環境変数の確認
    github_token = os.environ.get('GITHUB_TOKEN')
    slack_secret = os.environ.get('SLACK_SIGNING_SECRET')
    s3_bucket = os.environ.get('S3_BUCKET_NAME')
    
    print(f"Environment Variables:")
    print(f"   GitHub Token: {'✅ Set' if github_token else '❌ Not set'}")
    print(f"   Slack Secret: {'✅ Set' if slack_secret else '❌ Not set'}")
    print(f"   S3 Bucket: {'✅ Set' if s3_bucket else '❌ Not set (will be skipped)'}")
    
    # テスト実行
    results = {
        "Health Check": test_health_check(),
        "Root Endpoint": test_root_endpoint(),
        "Feedback Summary": test_feedback_summary(),
        "Slack Feedback": test_slack_feedback(),
        "Invalid Routes": test_invalid_routes()
    }
    
    # 結果サマリー
    print(f"\n🎯 Test Summary:")
    print("=" * 30)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print(f"\n🎉 All tests passed! Lambda function is ready for deployment.")
        print(f"\n💡 Next steps:")
        print(f"   1. Deploy to AWS: ./scripts/deploy-lambda.sh dev")
        print(f"   2. Configure Slack App Interactive Components")
        print(f"   3. Test with real Slack: uv run python src/main.py --slack-test-3")
    else:
        print(f"\n⚠️  Some tests failed. Please check the errors above.")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())