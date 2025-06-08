#!/usr/bin/env python3
"""
環境変数を .env ファイルから読み込むユーティリティ
使用方法: from scripts.load_env import load_env; load_env()
"""
import os
from pathlib import Path

def load_env():
    """プロジェクトルートの .env ファイルから環境変数を読み込む"""
    project_root = Path(__file__).parent.parent
    env_file = project_root / '.env'
    
    if not env_file.exists():
        print(f"Warning: .env file not found at {env_file}")
        return
    
    print(f"Loading environment variables from {env_file}")
    
    with open(env_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            
            # コメント行や空行をスキップ
            if not line or line.startswith('#'):
                continue
            
            # KEY=VALUE 形式をパース
            if '=' not in line:
                print(f"Warning: Invalid line {line_num} in .env: {line}")
                continue
            
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            
            # 既に環境変数が設定されている場合はスキップ
            if key in os.environ:
                print(f"Skipping {key} (already set in environment)")
                continue
            
            os.environ[key] = value
            print(f"Loaded: {key}")

if __name__ == "__main__":
    load_env()