#!/usr/bin/env python3
"""
src/config.py
Sports WINNER Quant Research Lab - 共通環境設定・動的パス解決モジュール
- 環境変数 WINNER_PROJECT_ROOT を最優先
- 設定されていない場合は本ファイルの親ディレクトリを動的に解決
- Mac/Linux/Windows 間の完全な可搬性 (Portability) を保証
"""

import os
import sys

def get_project_root() -> str:
    """プロジェクトルートディレクトリを動的に解決"""
    env_root = os.getenv("WINNER_PROJECT_ROOT")
    if env_root and os.path.isdir(env_root):
        return os.path.abspath(env_root)
    # 本ファイル (src/config.py) の親ディレクトリ
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

PROJECT_ROOT = get_project_root()

# sys.path にプロジェクトルートを追加
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 主要ディレクトリ
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
MODELS_DIR = os.path.join(DATA_DIR, "models")
RAW_DIR = os.path.join(DATA_DIR, "raw")
RAW_EVIDENCE_DIR = os.path.join(DATA_DIR, "raw_evidence")
ODDS_SNAPSHOT_DIR = os.path.join(DATA_DIR, "odds_snapshots")
REPORTS_DIR = os.path.join(PROJECT_ROOT, "reports")
TESTS_DIR = os.path.join(PROJECT_ROOT, "tests")

def resolve_path(relative_or_absolute_path: str) -> str:
    """
    パスをプロジェクトルート基準で解決
    - 相対パスの場合は PROJECT_ROOT と結合
    - 絶対パスでも現在の PROJECT_ROOT 配下または旧パスを含む場合は適切に再マッピング
    """
    if not relative_or_absolute_path:
        return ""
    if os.path.isabs(relative_or_absolute_path):
        if os.path.exists(relative_or_absolute_path):
            return relative_or_absolute_path
        # 旧Macパス等が含まれる場合はベース名または data/ 以降を抽出して再解決
        if "data/" in relative_or_absolute_path:
            rel = relative_or_absolute_path.split("data/", 1)[1]
            candidate = os.path.join(DATA_DIR, rel)
            if os.path.exists(candidate):
                return candidate
        # ファイル名単体での探索
        bname = os.path.basename(relative_or_absolute_path)
        for d in [RAW_EVIDENCE_DIR, ODDS_SNAPSHOT_DIR, MODELS_DIR, RAW_DIR, DATA_DIR]:
            candidate = os.path.join(d, bname)
            if os.path.exists(candidate):
                return candidate
        return relative_or_absolute_path
    return os.path.join(PROJECT_ROOT, relative_or_absolute_path)
