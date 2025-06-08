#!/usr/bin/env python3
"""
フィードバックハンドラーのテストスクリプト
Slack Interactive Components のペイロード形式をシミュレート
"""

import sys
import os
import json
from datetime import datetime

# パスを追加してsrcモジュールをインポート
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from feedback_handler import FeedbackHandler

def create_sample_slack_payload(feedback_type: str = "interested", article_num: int = 1) -> dict:
    """サンプルのSlackペイロードを作成"""
    
    articles = [
        {
            "id": "https://www.nature.com/articles/test-article-1",
            "title": "Revolutionary CRISPR technique enables precise gene editing in living organisms",
            "journal": "Nature",
            "authors": ["Dr. Jane Smith", "Dr. John Doe", "Dr. Alice Johnson"],
            "timestamp": datetime.now().isoformat()
        },
        {
            "id": "https://www.science.org/articles/test-article-2", 
            "title": "Quantum computing breakthrough achieves error correction milestone",
            "journal": "Science",
            "authors": ["Dr. Maria Garcia", "Dr. Robert Chen"],
            "timestamp": datetime.now().isoformat()
        },
        {
            "id": "https://www.nature.com/articles/test-article-3",
            "title": "Machine learning model predicts climate tipping points with 90% accuracy",
            "journal": "Nature",
            "authors": ["Dr. Sarah Wilson", "Dr. Michael Brown"],
            "timestamp": datetime.now().isoformat()
        }
    ]
    
    article = articles[article_num - 1]
    
    # Slack Interactive Components の実際のペイロード形式
    payload = {
        "type": "block_actions",
        "user": {
            "id": "U123456789",
            "username": "testuser",
            "name": "Test User"
        },
        "api_app_id": "A123456789",
        "token": "verification_token",
        "container": {
            "message_ts": "1234567890.123456"
        },
        "trigger_id": "123456789.987654321.abcdef1234567890",
        "team": {
            "id": "T123456789",
            "domain": "test-workspace"
        },
        "channel": {
            "id": "C123456789",
            "name": "論文-通知"
        },
        "response_url": "https://hooks.slack.com/actions/...",
        "actions": [
            {
                "action_id": f"feedback_{feedback_type}",
                "block_id": f"feedback_block_{article_num}",
                "text": {
                    "type": "plain_text",
                    "text": "👍 興味あり" if feedback_type == "interested" else "👎 興味なし",
                    "emoji": True
                },
                "value": json.dumps({
                    "feedback": feedback_type,
                    "article": article
                }),
                "type": "button",
                "action_ts": "1234567890.123456"
            }
        ]
    }
    
    return payload

def test_feedback_processing():
    """フィードバック処理のテスト"""
    print("🧪 Testing Feedback Handler...")
    
    handler = FeedbackHandler()
    
    # テスト1: 興味ありフィードバック
    print("\n1. Testing 'interested' feedback...")
    payload1 = create_sample_slack_payload("interested", 1)
    success1 = handler.process_slack_feedback(payload1)
    print(f"   Result: {'✅ Success' if success1 else '❌ Failed'}")
    
    # テスト2: 興味なしフィードバック
    print("\n2. Testing 'not_interested' feedback...")
    payload2 = create_sample_slack_payload("not_interested", 2)
    success2 = handler.process_slack_feedback(payload2)
    print(f"   Result: {'✅ Success' if success2 else '❌ Failed'}")
    
    # テスト3: 複数のフィードバック
    print("\n3. Testing multiple feedbacks...")
    payloads = [
        create_sample_slack_payload("interested", 3),
        create_sample_slack_payload("not_interested", 1),
        create_sample_slack_payload("interested", 2)
    ]
    
    for i, payload in enumerate(payloads, 1):
        success = handler.process_slack_feedback(payload)
        print(f"   Feedback {i}: {'✅ Success' if success else '❌ Failed'}")
    
    # テスト4: フィードバック統計
    print("\n4. Testing feedback summary...")
    summary = handler.get_feedback_summary(days=1)
    print(f"   Total feedbacks: {summary['total']}")
    print(f"   Interested: {summary['interested']}")
    print(f"   Not interested: {summary['not_interested']}")
    print(f"   Articles with feedback: {len(summary['articles'])}")
    
    return success1 and success2

def test_invalid_payloads():
    """無効なペイロードのテスト"""
    print("\n🧪 Testing Invalid Payloads...")
    
    handler = FeedbackHandler()
    
    # テスト1: 空のペイロード
    print("\n1. Testing empty payload...")
    empty_success = handler.process_slack_feedback({})
    print(f"   Result: {'✅ Handled gracefully' if not empty_success else '❌ Should have failed'}")
    
    # テスト2: 不正なJSON
    print("\n2. Testing invalid JSON in action value...")
    invalid_payload = {
        "actions": [{
            "action_id": "feedback_interested",
            "value": "invalid_json_here"
        }],
        "user": {"id": "U123", "name": "test"},
        "channel": {"id": "C123", "name": "test"}
    }
    invalid_success = handler.process_slack_feedback(invalid_payload)
    print(f"   Result: {'✅ Handled gracefully' if not invalid_success else '❌ Should have failed'}")
    
    return True

def show_feedback_log():
    """フィードバックログを表示"""
    log_file = "data/feedback_log.jsonl"
    
    if not os.path.exists(log_file):
        print(f"\n📝 No feedback log found at {log_file}")
        return
    
    print(f"\n📝 Feedback Log Contents ({log_file}):")
    print("=" * 80)
    
    with open(log_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            try:
                feedback = json.loads(line)
                timestamp = feedback['timestamp'][:19]  # Remove microseconds
                article_title = feedback['article']['title'][:60]
                feedback_type = '👍' if feedback['feedback'] == 'interested' else '👎'
                user_name = feedback['user']['name']
                
                print(f"{i:2d}. {timestamp} | {feedback_type} | {user_name:10s} | {article_title}...")
                
            except json.JSONDecodeError:
                print(f"{i:2d}. [Invalid JSON line]")
    
    print("=" * 80)

def main():
    """メイン実行関数"""
    print("🚀 RSS AI Reporter - Feedback Handler Test")
    print("=" * 60)
    
    # 環境変数の確認
    github_token = os.environ.get('GITHUB_TOKEN')
    print(f"GitHub Token: {'✅ Configured' if github_token else '❌ Not configured (will log locally only)'}")
    
    slack_secret = os.environ.get('SLACK_SIGNING_SECRET')
    print(f"Slack Secret: {'✅ Configured' if slack_secret else '❌ Not configured (will skip verification)'}")
    
    github_repo = os.environ.get('GITHUB_REPO', 'dakesan/rss_ai_reporter')
    print(f"GitHub Repo: {github_repo}")
    
    # テスト実行
    success = test_feedback_processing()
    test_invalid_payloads()
    
    # ログ表示
    show_feedback_log()
    
    # 結果サマリー
    print(f"\n🎯 Test Summary:")
    print(f"   Overall: {'✅ All tests passed' if success else '❌ Some tests failed'}")
    print(f"   Log file: data/feedback_log.jsonl")
    if github_token:
        print(f"   GitHub Issues: Check {github_repo}/issues for new feedback issues")
    
    print("\n💡 Next steps:")
    print("   1. Set up Slack App Interactive Components")
    print("   2. Configure Request URL: https://your-domain.com/slack/feedback")
    print("   3. Test with real Slack feedback buttons: python src/main.py --slack-test-3")

if __name__ == "__main__":
    main()