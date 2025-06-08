#!/usr/bin/env python3
"""
新ジャーナル追加時の互換性テストスクリプト
"""
import sys
import os
import subprocess
import json
from datetime import datetime

def test_journal_compatibility(journal_name: str = None, gemini_only: bool = False):
    """ジャーナル互換性テストを実行"""
    
    print(f"🧪 Starting Journal Compatibility Tests")
    print(f"📅 Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if journal_name:
        print(f"🎯 Target Journal: {journal_name}")
    if gemini_only:
        print(f"🤖 Gemini API tests only")
    
    print("=" * 60)
    
    # 環境確認
    print("🔍 Environment Check:")
    
    # Gemini API Key確認
    if os.environ.get('GEMINI_API_KEY'):
        print("   ✅ GEMINI_API_KEY: Set")
    else:
        print("   ❌ GEMINI_API_KEY: Not set")
        if gemini_only:
            print("   ⚠️  Warning: Gemini tests will be skipped")
    
    # Python dependencies確認
    required_packages = ['requests', 'beautifulsoup4', 'feedparser', 'google-generativeai']
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"   ✅ {package}: Available")
        except ImportError:
            print(f"   ❌ {package}: Missing")
    
    print()
    
    # テスト実行
    test_file = os.path.join(os.path.dirname(__file__), '..', 'test', 'test_new_journals.py')
    
    cmd = [sys.executable, test_file]
    
    if journal_name:
        cmd.extend(['--journal', journal_name])
    
    if gemini_only:
        cmd.append('--gemini-only')
    
    print(f"🚀 Running command: {' '.join(cmd)}")
    print()
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        print("📊 Test Results:")
        print("-" * 40)
        print(result.stdout)
        
        if result.stderr:
            print("⚠️ Warnings/Errors:")
            print(result.stderr)
        
        success = result.returncode == 0
        
        print("=" * 60)
        if success:
            print("✅ All tests passed!")
        else:
            print("❌ Some tests failed!")
        
        return success
        
    except subprocess.TimeoutExpired:
        print("⏰ Tests timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

def generate_test_report(results: dict):
    """テスト結果レポートを生成"""
    report = {
        "test_date": datetime.now().isoformat(),
        "results": results,
        "summary": {
            "total_journals": len(results),
            "passed": sum(1 for r in results.values() if r),
            "failed": sum(1 for r in results.values() if not r)
        }
    }
    
    report_file = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"📄 Test report saved: {report_file}")
    return report_file

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='新ジャーナル互換性テスト実行')
    parser.add_argument('--journal', choices=['cell', 'nejm', 'pnas', 'arxiv', 'plos'],
                       help='特定ジャーナルのテストのみ実行')
    parser.add_argument('--gemini-only', action='store_true',
                       help='Gemini互換性テストのみ実行')
    parser.add_argument('--all-journals', action='store_true',
                       help='全ジャーナルを個別にテスト')
    parser.add_argument('--report', action='store_true',
                       help='テスト結果レポートを生成')
    
    args = parser.parse_args()
    
    if args.all_journals:
        # 全ジャーナルを個別テスト
        journals = ['cell', 'nejm', 'pnas', 'arxiv', 'plos']
        results = {}
        
        for journal in journals:
            print(f"\n🔬 Testing {journal.upper()}...")
            success = test_journal_compatibility(journal, args.gemini_only)
            results[journal] = success
        
        if args.report:
            generate_test_report(results)
        
        # 総合結果
        total_passed = sum(results.values())
        total_journals = len(results)
        
        print(f"\n📋 Overall Results: {total_passed}/{total_journals} journals passed")
        
        if total_passed == total_journals:
            print("🎉 All journal tests passed!")
            sys.exit(0)
        else:
            print("⚠️ Some journal tests failed!")
            sys.exit(1)
    
    else:
        # 単一実行
        success = test_journal_compatibility(args.journal, args.gemini_only)
        sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()