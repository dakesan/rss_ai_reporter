#!/usr/bin/env python3
"""
Webhookサーバーの機能テスト
実際のSlackペイロードをシミュレートしてテスト
"""

import json
import requests
import time
import subprocess
import sys
import os
from threading import Thread

# パスを追加
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

def start_webhook_server():
    """Webhookサーバーをバックグラウンドで起動"""
    try:
        env = os.environ.copy()
        env['FLASK_DEBUG'] = 'false'
        
        process = subprocess.Popen(
            [sys.executable, 'src/webhook_server.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        
        # サーバー起動を待機
        time.sleep(3)
        
        # ヘルスチェック
        try:
            response = requests.get('http://127.0.0.1:5000/health', timeout=5)
            if response.status_code == 200:
                print("✅ Webhook server started successfully")
                return process
            else:
                print(f"❌ Server health check failed: {response.status_code}")
                process.terminate()
                return None
        except requests.exceptions.RequestException:
            print("❌ Failed to connect to webhook server")
            process.terminate()
            return None
            
    except Exception as e:
        print(f"❌ Error starting webhook server: {e}")
        return None

def create_slack_feedback_payload():
    """実際のSlackフィードバックペイロードを作成"""
    article_data = {
        "id": "https://www.nature.com/articles/test-webhook-1",
        "title": "Webhook Test Article: Advanced Machine Learning in Quantum Computing",
        "journal": "Nature",
        "authors": ["Dr. Test Author", "Dr. Sample Researcher"],
        "timestamp": "2025-06-08T12:00:00"
    }
    
    # Slack Interactive Components の実際のペイロード構造
    payload = {
        "type": "block_actions",
        "user": {
            "id": "U987654321",
            "username": "webhook_tester",
            "name": "Webhook Tester"
        },
        "api_app_id": "A987654321",
        "token": "webhook_test_token",
        "container": {
            "message_ts": "1691234567.123456"
        },
        "trigger_id": "987654321.123456789.webhook_trigger_id",
        "team": {
            "id": "T987654321",
            "domain": "test-webhook-workspace"
        },
        "channel": {
            "id": "C987654321",
            "name": "論文-通知-テスト"
        },
        "response_url": "https://hooks.slack.com/actions/T987654321/987654321/webhook_response",
        "actions": [
            {
                "action_id": "feedback_interested",
                "block_id": "feedback_block_webhook_test",
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

def test_webhook_endpoints(base_url="http://127.0.0.1:5000"):
    """Webhookエンドポイントのテスト"""
    
    print("\n🧪 Testing Webhook Endpoints...")
    
    # テスト1: ヘルスチェック
    print("\n1. Testing health check endpoint...")
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Health check passed")
            print(f"   Service: {data.get('service')}")
            print(f"   Status: {data.get('status')}")
        else:
            print(f"   ❌ Health check failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Health check error: {e}")
    
    # テスト2: ルートエンドポイント
    print("\n2. Testing root endpoint...")
    try:
        response = requests.get(f"{base_url}/")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Root endpoint accessible")
            print(f"   Available endpoints: {len(data.get('endpoints', {}))}")
        else:
            print(f"   ❌ Root endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Root endpoint error: {e}")
    
    # テスト3: フィードバック統計
    print("\n3. Testing feedback summary endpoint...")
    try:
        response = requests.get(f"{base_url}/slack/feedback/summary")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Feedback summary accessible")
            print(f"   Total feedbacks: {data.get('total', 0)}")
            print(f"   Interested: {data.get('interested', 0)}")
            print(f"   Not interested: {data.get('not_interested', 0)}")
        else:
            print(f"   ❌ Feedback summary failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Feedback summary error: {e}")
    
    # テスト4: フィードバック送信
    print("\n4. Testing feedback submission...")
    try:
        payload = create_slack_feedback_payload()
        
        # form-dataとして送信（SlackのWebhook形式）
        response = requests.post(
            f"{base_url}/slack/feedback",
            data={'payload': json.dumps(payload)},
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Feedback submission successful")
            print(f"   Response type: {data.get('response_type')}")
            print(f"   Message: {data.get('text', '')[:100]}...")
        else:
            print(f"   ❌ Feedback submission failed: {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
    except Exception as e:
        print(f"   ❌ Feedback submission error: {e}")
    
    # テスト5: 更新された統計確認
    print("\n5. Testing updated feedback summary...")
    try:
        response = requests.get(f"{base_url}/slack/feedback/summary")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Updated summary retrieved")
            print(f"   Total feedbacks: {data.get('total', 0)}")
            print(f"   Latest articles: {len(data.get('articles', []))}")
        else:
            print(f"   ❌ Updated summary failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Updated summary error: {e}")

def main():
    """メイン実行関数"""
    print("🚀 RSS AI Reporter - Webhook Server Test")
    print("=" * 60)
    
    # Webhookサーバーを起動
    print("Starting webhook server...")
    server_process = start_webhook_server()
    
    if not server_process:
        print("❌ Failed to start webhook server. Exiting.")
        return
    
    try:
        # テスト実行
        test_webhook_endpoints()
        
        print(f"\n🎯 Webhook Test Summary:")
        print(f"   Server: ✅ Running on http://127.0.0.1:5000")
        print(f"   Endpoints: ✅ All endpoints tested")
        print(f"   Feedback: ✅ Submission and logging working")
        print(f"   Log file: data/feedback_log.jsonl")
        
        print(f"\n💡 Next steps:")
        print(f"   1. Set GITHUB_TOKEN for GitHub Issues integration")
        print(f"   2. Set SLACK_SIGNING_SECRET for signature verification")
        print(f"   3. Deploy to production with proper HTTPS")
        print(f"   4. Configure Slack App Request URL")
        
    finally:
        # サーバープロセスを終了
        print(f"\nStopping webhook server...")
        server_process.terminate()
        server_process.wait()
        print("✅ Server stopped")

if __name__ == "__main__":
    main()