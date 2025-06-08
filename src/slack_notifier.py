import requests
import json
import os
from typing import List, Dict, Any
from datetime import datetime

class SlackNotifier:
    def __init__(self, enable_feedback: bool = False):
        self.webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
        if not self.webhook_url:
            raise ValueError("SLACK_WEBHOOK_URL environment variable is not set")
        self.enable_feedback = enable_feedback
    
    def format_message(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        print(f"  Formatting Slack message for {len(articles)} articles...")
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📚 今日の論文レポート（Nature & Science）- {datetime.now().strftime('%Y年%m月%d日')}",
                    "emoji": True
                }
            }
        ]
        
        # 各論文のブロックを作成
        for i, article in enumerate(articles):
            # summary_jaフィールドの存在確認
            summary_ja = article.get('summary_ja', '')
            if not summary_ja:
                print(f"  WARNING: Article {i+1} missing summary_ja field")
                print(f"    Available fields: {list(article.keys())}")
                summary_ja = "要約が生成されませんでした。"
            else:
                print(f"  Article {i+1}: summary_ja present ({len(summary_ja)} chars)")
            
            # 番号付きの絵文字
            number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
            number_emoji = number_emojis[i] if i < 10 else f"{i+1}."
            
            # 著者グループ名の整形
            authors = article.get('authors', [])
            if authors:
                if len(authors) > 2:
                    author_group = f"{authors[0]} et al."
                else:
                    author_group = " & ".join(authors)
            else:
                author_group = "著者情報なし"
            
            # 論文ブロック
            article_blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{number_emoji} *{article.get('title', 'タイトルなし')}*\n👥 {author_group}"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"📝 {summary_ja}"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"🔗 <{article.get('link', '#')}|論文を読む>"
                    }
                }
            ]
            
            blocks.extend(article_blocks)
            
            # フィードバックボタンを追加（有効な場合）
            if self.enable_feedback:
                feedback_block = self._create_feedback_buttons(article, i+1)
                blocks.append(feedback_block)
            
            # 論文間の区切り線（最後の論文以外）
            if i < len(articles) - 1:
                blocks.append({"type": "divider"})
        
        return {"blocks": blocks}
    
    def _create_feedback_buttons(self, article: Dict[str, Any], article_num: int) -> Dict[str, Any]:
        """フィードバックボタンのブロックを作成"""
        article_id = article.get('id', article.get('link', f'unknown_{article_num}'))
        
        # 記事データをコンパクトに格納
        article_data = {
            "id": article_id,
            "title": article.get('title', '')[:100],  # タイトルを100文字に制限
            "journal": article.get('journal', ''),
            "authors": article.get('authors', [])[:3],  # 著者を最大3名に制限
            "timestamp": datetime.now().isoformat()
        }
        
        return {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "👍 興味あり",
                        "emoji": True
                    },
                    "style": "primary",
                    "action_id": "feedback_interested",
                    "value": json.dumps({
                        "feedback": "interested",
                        "article": article_data
                    })
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text", 
                        "text": "👎 興味なし",
                        "emoji": True
                    },
                    "action_id": "feedback_not_interested",
                    "value": json.dumps({
                        "feedback": "not_interested",
                        "article": article_data
                    })
                }
            ]
        }
    
    def send_notification(self, articles: List[Dict[str, Any]]) -> bool:
        if not articles:
            print("No articles to notify")
            return True
        
        message = self.format_message(articles)
        
        try:
            response = requests.post(
                self.webhook_url,
                json=message,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                print(f"Successfully sent notification for {len(articles)} articles")
                return True
            else:
                print(f"Failed to send notification: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"Error sending Slack notification: {str(e)}")
            return False
    
    def send_error_notification(self, error_message: str):
        message = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "⚠️ 論文サマライザーエラー",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"エラーが発生しました:\n```{error_message}```"
                    }
                }
            ]
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=message,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code != 200:
                print(f"Failed to send error notification: {response.status_code}")
                
        except Exception as e:
            print(f"Error sending error notification: {str(e)}")