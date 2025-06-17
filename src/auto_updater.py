#!/usr/bin/env python3
"""
自動フィルター更新エンジン

フィードバック分析結果を基に filter_config.json を自動更新し、
GitHub PR を作成して人間のレビューを促す。
"""

import json
import os
import subprocess
import tempfile
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

from feedback_analyzer import FeedbackAnalyzer


class AutoFilterUpdater:
    """フィルター設定の自動更新エンジン"""
    
    def __init__(self, debug: bool = False, dry_run: bool = False):
        """
        Args:
            debug: デバッグモード
            dry_run: 実際の変更を行わないテストモード
        """
        self.debug = debug
        self.dry_run = dry_run
        self.logger = self._setup_logger()
        
        # パス設定
        self.base_dir = os.path.dirname(os.path.dirname(__file__))
        self.filter_config_path = os.path.join(self.base_dir, 'data', 'filter_config.json')
        
        # Git/GitHub設定
        self.git_config = self._load_git_config()
    
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
    
    def _load_git_config(self) -> Dict:
        """Git設定を読み込む"""
        try:
            # リモートリポジトリ情報を取得
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'], 
                capture_output=True, text=True, check=True
            )
            remote_url = result.stdout.strip()
            
            # GitHub リポジトリ名を抽出
            if 'github.com' in remote_url:
                if remote_url.startswith('git@'):
                    # SSH形式: git@github.com:user/repo.git
                    repo_part = remote_url.split(':')[1].replace('.git', '')
                else:
                    # HTTPS形式: https://github.com/user/repo.git
                    repo_part = remote_url.split('github.com/')[1].replace('.git', '')
                
                return {
                    'remote_url': remote_url,
                    'repo': repo_part,
                    'base_branch': 'main'
                }
            else:
                raise ValueError("GitHub repository not detected")
                
        except Exception as e:
            self.logger.error(f"Failed to load git config: {e}")
            return {
                'remote_url': '',
                'repo': 'unknown/unknown',
                'base_branch': 'main'
            }
    
    def _run_command(self, command: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """コマンドを実行"""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would execute: {' '.join(command)}")
            return subprocess.CompletedProcess(command, 0, '', '')
        
        self.logger.debug(f"Executing: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True, check=check)
        
        if result.stdout:
            self.logger.debug(f"STDOUT: {result.stdout}")
        if result.stderr:
            self.logger.debug(f"STDERR: {result.stderr}")
            
        return result
    
    def check_prerequisites(self) -> bool:
        """前提条件をチェック"""
        self.logger.info("Checking prerequisites...")
        
        # GitHub CLI の確認
        try:
            result = self._run_command(['gh', '--version'], check=False)
            if result.returncode != 0:
                self.logger.error("GitHub CLI (gh) is not installed or not in PATH")
                return False
            self.logger.debug(f"GitHub CLI: {result.stdout.strip()}")
        except FileNotFoundError:
            self.logger.error("GitHub CLI (gh) command not found")
            return False
        
        # Git 認証確認
        try:
            result = self._run_command(['git', 'status', '--porcelain'], check=False)
            if result.returncode != 0:
                self.logger.error("Not in a git repository or git not available")
                return False
        except FileNotFoundError:
            self.logger.error("Git command not found")
            return False
        
        # GitHub 認証確認
        try:
            result = self._run_command(['gh', 'auth', 'status'], check=False)
            if result.returncode != 0:
                self.logger.error("GitHub CLI not authenticated. Run: gh auth login")
                return False
            self.logger.debug("GitHub CLI authenticated")
        except Exception as e:
            self.logger.error(f"GitHub authentication check failed: {e}")
            return False
        
        # filter_config.json の存在確認
        if not os.path.exists(self.filter_config_path):
            self.logger.error(f"Filter config not found: {self.filter_config_path}")
            return False
        
        self.logger.info("✅ All prerequisites satisfied")
        return True
    
    def should_auto_update(self, analysis_result: Dict) -> Tuple[bool, str]:
        """
        分析結果に基づいて自動更新すべきかどうかを判定
        
        Args:
            analysis_result: フィードバック分析結果
            
        Returns:
            (should_update, reason)
        """
        if analysis_result['status'] != 'success':
            return False, f"Analysis failed: {analysis_result.get('message', 'Unknown error')}"
        
        # データ量チェック
        data_count = analysis_result['data_count']
        if data_count < 5:
            return False, f"Insufficient feedback data: {data_count} < 5"
        
        # 信頼度チェック
        recommendations = analysis_result['filter_recommendations']
        confidence = recommendations.get('confidence', 0)
        if confidence < 6:
            return False, f"Low confidence score: {confidence} < 6"
        
        # 提案されるキーワードの確認
        suggested_additions = recommendations['suggested_additions']
        new_includes = suggested_additions.get('include', [])
        new_excludes = suggested_additions.get('exclude', [])
        
        if not new_includes and not new_excludes:
            return False, "No new keywords suggested"
        
        # 過度な変更の防止
        total_changes = len(new_includes) + len(new_excludes)
        if total_changes > 20:
            return False, f"Too many changes suggested: {total_changes} > 20"
        
        return True, f"Confidence: {confidence}/10, Changes: {total_changes}, Data: {data_count} entries"
    
    def create_filter_update(self, analysis_result: Dict) -> Dict:
        """
        分析結果に基づいてフィルター更新内容を作成
        
        Args:
            analysis_result: フィードバック分析結果
            
        Returns:
            更新内容の詳細
        """
        recommendations = analysis_result['filter_recommendations']
        current_filters = recommendations['current_filters']
        suggested_additions = recommendations['suggested_additions']
        
        # 更新されたフィルター設定を作成
        updated_filters = current_filters.copy()
        
        # 新しいキーワードを追加
        current_includes = set(updated_filters.get('include', []))
        current_excludes = set(updated_filters.get('exclude', []))
        
        new_includes = suggested_additions.get('include', [])
        new_excludes = suggested_additions.get('exclude', [])
        
        # 重複排除して追加
        for keyword in new_includes:
            if keyword not in current_includes:
                current_includes.add(keyword)
        
        for keyword in new_excludes:
            if keyword not in current_excludes:
                current_excludes.add(keyword)
        
        updated_filters['include'] = sorted(list(current_includes))
        updated_filters['exclude'] = sorted(list(current_excludes))
        
        return {
            'original': current_filters,
            'updated': updated_filters,
            'changes': {
                'added_includes': new_includes,
                'added_excludes': new_excludes
            },
            'analysis_summary': analysis_result['ai_analysis'].get('summary', ''),
            'reasoning': recommendations.get('reasoning', ''),
            'confidence': recommendations.get('confidence', 0),
            'data_count': analysis_result['data_count']
        }
    
    def create_auto_update_branch(self, update_info: Dict) -> str:
        """
        自動更新用のブランチを作成
        
        Args:
            update_info: 更新情報
            
        Returns:
            作成されたブランチ名
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        branch_name = f"auto-update-filters-{timestamp}"
        
        self.logger.info(f"Creating auto-update branch: {branch_name}")
        
        # mainブランチの最新を取得
        self._run_command(['git', 'fetch', 'origin'])
        self._run_command(['git', 'checkout', self.git_config['base_branch']])
        self._run_command(['git', 'pull', 'origin', self.git_config['base_branch']])
        
        # 新しいブランチを作成
        self._run_command(['git', 'checkout', '-b', branch_name])
        
        return branch_name
    
    def update_filter_config(self, update_info: Dict) -> bool:
        """
        filter_config.json を更新
        
        Args:
            update_info: 更新情報
            
        Returns:
            更新成功かどうか
        """
        try:
            if self.dry_run:
                self.logger.info("[DRY RUN] Would update filter_config.json")
                self.logger.info(f"Changes: {json.dumps(update_info['changes'], indent=2, ensure_ascii=False)}")
                return True
            
            # バックアップ作成
            backup_path = f"{self.filter_config_path}.backup"
            shutil.copy2(self.filter_config_path, backup_path)
            self.logger.debug(f"Created backup: {backup_path}")
            
            # 新しい設定を書き込み
            with open(self.filter_config_path, 'w', encoding='utf-8') as f:
                json.dump(update_info['updated'], f, indent=2, ensure_ascii=False)
                f.write('\n')  # 末尾に改行追加
            
            self.logger.info("✅ Filter config updated successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update filter config: {e}")
            return False
    
    def commit_and_push(self, branch_name: str, update_info: Dict) -> bool:
        """
        変更をコミットしてプッシュ
        
        Args:
            branch_name: ブランチ名
            update_info: 更新情報
            
        Returns:
            成功かどうか
        """
        try:
            # ステージング
            self._run_command(['git', 'add', self.filter_config_path])
            
            # コミットメッセージ作成
            changes = update_info['changes']
            added_includes = changes['added_includes']
            added_excludes = changes['added_excludes']
            
            commit_msg_lines = [
                "feat: AI分析によるフィルター自動更新",
                "",
                f"📊 分析データ: {update_info['data_count']} feedback entries",
                f"🎯 信頼度スコア: {update_info['confidence']}/10",
            ]
            
            if added_includes:
                commit_msg_lines.append(f"➕ 追加されたINCLUDEキーワード: {', '.join(added_includes)}")
            if added_excludes:
                commit_msg_lines.append(f"➖ 追加されたEXCLUDEキーワード: {', '.join(added_excludes)}")
            
            commit_msg_lines.extend([
                "",
                f"💡 AI分析結果: {update_info['analysis_summary'][:100]}...",
                f"📝 推奨理由: {update_info['reasoning'][:100]}...",
                "",
                "🤖 Generated with [Claude Code](https://claude.ai/code)",
                "",
                "Co-Authored-By: Claude <noreply@anthropic.com>"
            ])
            
            commit_msg = '\n'.join(commit_msg_lines)
            
            # コミット実行
            self._run_command(['git', 'commit', '-m', commit_msg])
            
            # プッシュ
            self._run_command(['git', 'push', '-u', 'origin', branch_name])
            
            self.logger.info("✅ Changes committed and pushed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to commit and push: {e}")
            return False
    
    def create_pull_request(self, branch_name: str, update_info: Dict) -> Optional[str]:
        """
        プルリクエストを作成
        
        Args:
            branch_name: ブランチ名
            update_info: 更新情報
            
        Returns:
            PR URL または None
        """
        try:
            changes = update_info['changes']
            added_includes = changes['added_includes']
            added_excludes = changes['added_excludes']
            
            # PR タイトル
            title = f"feat: AI分析によるフィルター自動更新 (信頼度: {update_info['confidence']}/10)"
            
            # PR 本文
            body_lines = [
                "## 📊 AI分析によるフィルター自動更新",
                "",
                "### 📈 分析結果サマリー",
                f"- **分析データ**: {update_info['data_count']} feedback entries",
                f"- **信頼度スコア**: {update_info['confidence']}/10",
                f"- **変更数**: {len(added_includes) + len(added_excludes)} keywords",
                "",
                "### 🎯 提案された変更",
            ]
            
            if added_includes:
                body_lines.append("#### ➕ 追加されるINCLUDEキーワード")
                for keyword in added_includes:
                    body_lines.append(f"- `{keyword}`")
                body_lines.append("")
            
            if added_excludes:
                body_lines.append("#### ➖ 追加されるEXCLUDEキーワード") 
                for keyword in added_excludes:
                    body_lines.append(f"- `{keyword}`")
                body_lines.append("")
            
            body_lines.extend([
                "### 🤖 AI分析詳細",
                f"**分析サマリー**: {update_info['analysis_summary']}",
                "",
                f"**推奨理由**: {update_info['reasoning']}",
                "",
                "### ✅ レビューポイント",
                "- [ ] 追加されるキーワードが適切か確認",
                "- [ ] 既存のキーワードとの重複や矛盾がないか確認", 
                "- [ ] ユーザーの興味傾向と一致しているか確認",
                "",
                "### 🚀 マージ後の効果",
                "このPRをマージすると、今後の論文フィルタリングで以下の改善が期待されます：",
                "- より精度の高い論文推奨",
                "- ユーザーの興味に合った論文の選択",
                "- 不要な論文の除外強化",
                "",
                "🤖 Generated with [Claude Code](https://claude.ai/code)"
            ])
            
            body = '\n'.join(body_lines)
            
            # PR作成
            result = self._run_command([
                'gh', 'pr', 'create',
                '--title', title,
                '--body', body,
                '--base', self.git_config['base_branch']
            ])
            
            if not self.dry_run:
                pr_url = result.stdout.strip()
                self.logger.info(f"✅ Pull request created: {pr_url}")
                return pr_url
            else:
                self.logger.info("[DRY RUN] Would create pull request")
                return "https://github.com/example/repo/pull/123"
                
        except Exception as e:
            self.logger.error(f"Failed to create pull request: {e}")
            return None
    
    def run_auto_update(self, 
                       days: int = 30, 
                       min_feedback: int = 5,
                       min_confidence: int = 6) -> Dict:
        """
        自動更新プロセスを実行
        
        Args:
            days: 分析対象期間（日数）
            min_feedback: 最小フィードバック数
            min_confidence: 最小信頼度スコア
            
        Returns:
            実行結果
        """
        self.logger.info("🚀 Starting auto filter update process...")
        
        try:
            # 前提条件チェック
            if not self.check_prerequisites():
                return {
                    'status': 'error',
                    'message': 'Prerequisites not satisfied',
                    'stage': 'prerequisites'
                }
            
            # フィードバック分析実行
            self.logger.info("📊 Running feedback analysis...")
            analyzer = FeedbackAnalyzer(debug=self.debug)
            analysis_result = analyzer.run_analysis(
                days=days, 
                min_feedback=min_feedback
            )
            
            # 自動更新判定
            should_update, reason = self.should_auto_update(analysis_result)
            if not should_update:
                return {
                    'status': 'skipped',
                    'message': reason,
                    'stage': 'analysis',
                    'analysis_result': analysis_result
                }
            
            self.logger.info(f"✅ Auto-update approved: {reason}")
            
            # 更新内容作成
            update_info = self.create_filter_update(analysis_result)
            
            # ブランチ作成
            branch_name = self.create_auto_update_branch(update_info)
            
            # フィルター設定更新
            if not self.update_filter_config(update_info):
                return {
                    'status': 'error',
                    'message': 'Failed to update filter config',
                    'stage': 'update'
                }
            
            # コミット&プッシュ
            if not self.commit_and_push(branch_name, update_info):
                return {
                    'status': 'error',
                    'message': 'Failed to commit and push changes',
                    'stage': 'git'
                }
            
            # プルリクエスト作成
            pr_url = self.create_pull_request(branch_name, update_info)
            if not pr_url:
                return {
                    'status': 'error',
                    'message': 'Failed to create pull request',
                    'stage': 'pr'
                }
            
            return {
                'status': 'success',
                'message': 'Auto-update completed successfully',
                'branch_name': branch_name,
                'pr_url': pr_url,
                'update_info': update_info,
                'analysis_result': analysis_result
            }
            
        except Exception as e:
            self.logger.error(f"Auto-update failed: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()
            
            return {
                'status': 'error',
                'message': f'Unexpected error: {e}',
                'stage': 'unknown'
            }


def main():
    """メイン関数 - CLIテスト用"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Auto Filter Updater')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode (no actual changes)')
    parser.add_argument('--days', type=int, default=30, help='Analysis period in days')
    parser.add_argument('--min-feedback', type=int, default=5, help='Minimum feedback count')
    parser.add_argument('--min-confidence', type=int, default=6, help='Minimum confidence score')
    
    args = parser.parse_args()
    
    try:
        updater = AutoFilterUpdater(debug=args.debug, dry_run=args.dry_run)
        result = updater.run_auto_update(
            days=args.days,
            min_feedback=args.min_feedback,
            min_confidence=args.min_confidence
        )
        
        print("=" * 60)
        print("🔄 AUTO FILTER UPDATE RESULTS")
        print("=" * 60)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        if result['status'] == 'success':
            print(f"\n✅ Success! PR created: {result['pr_url']}")
            return 0
        elif result['status'] == 'skipped':
            print(f"\n⏭️  Skipped: {result['message']}")
            return 0
        else:
            print(f"\n❌ Failed: {result['message']}")
            return 1
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == '__main__':
    exit(main())