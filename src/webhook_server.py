#!/usr/bin/env python3
"""
Slack Interactive Components用Webhookサーバー
フィードバックボタンのクリックを受信してGitHub Issuesに記録
"""

import os
import json
import hmac
import hashlib
from typing import Dict, Any
from flask import Flask, request, jsonify
from feedback_handler import FeedbackHandler

app = Flask(__name__)
feedback_handler = FeedbackHandler()

def verify_slack_signature(request_body: bytes, timestamp: str, signature: str) -> bool:
    """Slackからのリクエストの署名を検証"""
    signing_secret = os.environ.get('SLACK_SIGNING_SECRET')
    if not signing_secret:
        print("WARNING: SLACK_SIGNING_SECRET not set, skipping signature verification")
        return True
    
    # Slackの署名検証
    sig_basestring = f"v0:{timestamp}:{request_body.decode('utf-8')}"
    my_signature = 'v0=' + hmac.new(
        signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(my_signature, signature)

@app.route('/slack/feedback', methods=['POST'])
def handle_slack_feedback():
    """Slackフィードバックボタンのクリックを処理"""
    try:
        # リクエストの署名を検証
        timestamp = request.headers.get('X-Slack-Request-Timestamp', '')
        signature = request.headers.get('X-Slack-Signature', '')
        
        if not verify_slack_signature(request.get_data(), timestamp, signature):
            return jsonify({'error': 'Invalid signature'}), 401
        
        # Content-Typeに応じてペイロードを解析
        if request.content_type == 'application/json':
            payload = request.json
        else:
            # application/x-www-form-urlencodedの場合
            payload_str = request.form.get('payload', '')
            if not payload_str:
                return jsonify({'error': 'No payload found'}), 400
            payload = json.loads(payload_str)
        
        print(f"Received feedback payload: {payload.get('type', 'unknown')}")
        
        # フィードバックを処理
        success = feedback_handler.process_slack_feedback(payload)
        
        if success:
            # Slackへの応答メッセージ
            response_message = _create_response_message(payload)
            return jsonify(response_message)
        else:
            return jsonify({'error': 'Failed to process feedback'}), 500
            
    except Exception as e:
        print(f"Error handling Slack feedback: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

def _create_response_message(payload: Dict[str, Any]) -> Dict[str, Any]:
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
            "response_type": "ephemeral",  # 本人のみに表示
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

@app.route('/slack/feedback/summary', methods=['GET'])
def get_feedback_summary():
    """フィードバック統計の確認用エンドポイント"""
    try:
        days = request.args.get('days', 7, type=int)
        summary = feedback_handler.get_feedback_summary(days=days)
        return jsonify(summary)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """ヘルスチェック用エンドポイント"""
    return jsonify({
        'status': 'ok',
        'service': 'RSS AI Reporter Feedback Server',
        'github_token': 'configured' if feedback_handler.github_token else 'not_configured',
        'slack_secret': 'configured' if feedback_handler.slack_signing_secret else 'not_configured'
    })

@app.route('/', methods=['GET'])
def index():
    """ルートエンドポイント"""
    return jsonify({
        'service': 'RSS AI Reporter Feedback Server',
        'endpoints': {
            '/slack/feedback': 'POST - Slack Interactive Components webhook',
            '/slack/feedback/summary': 'GET - Feedback statistics',
            '/health': 'GET - Health check'
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    print(f"Starting RSS AI Reporter Feedback Server on port {port}")
    print(f"GitHub Token: {'✅ Configured' if feedback_handler.github_token else '❌ Not configured'}")
    print(f"Slack Secret: {'✅ Configured' if feedback_handler.slack_signing_secret else '❌ Not configured'}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)