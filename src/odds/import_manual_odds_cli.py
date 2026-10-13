#!/usr/bin/env python3
"""
src/odds/import_manual_odds_cli.py
Phase 6: 公式オッズ手動入力 CLI ツール
使用例:
  ./venv/bin/python src/odds/import_manual_odds_cli.py \
    --lottery-id 10247 \
    --sport Basketball \
    --observed-time "2026-10-14T08:30:00Z" \
    --source-url "https://winner.toto.rakuten.co.jp/detail/singlematch/10247/" \
    --odds-file path/to/odds.json \
    --evidence-file path/to/page.html \
    --verify
"""

import os
import sys
import json
import argparse

BASE_DIR = os.getenv("WINNER_PROJECT_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.odds.odds_snapshot_manager import RealOddsSnapshotManager

def main():
    parser = argparse.ArgumentParser(description="WINNER Manual Odds Importer (Phase 6)")
    parser.add_argument("--lottery-id", required=True, help="Official lottery ID (e.g. 10247)")
    parser.add_argument("--sport", required=True, choices=["Basketball", "Soccer"], help="Sport")
    parser.add_argument("--observed-time", required=True, help="ISO8601 UTC timestamp of observation")
    parser.add_argument("--source-url", default="https://winner.toto.rakuten.co.jp/", help="Official page URL")
    parser.add_argument("--odds-file", required=True, help="JSON file mapping choice numbers (1..16 or 1..18) to float odds")
    parser.add_argument("--evidence-file", required=True, help="Primary source file (HTML/screenshot/txt)")
    parser.add_argument("--verify", action="store_true", help="Flag indicating manual primary source verification is complete")

    args = parser.parse_args()

    # オッズファイル読み込み
    with open(args.odds_file, "r", encoding="utf-8") as f:
        raw_odds = json.load(f)
    odds_dict = {int(k): float(v) for k, v in raw_odds.items()}

    # 証拠ファイル読み込み
    with open(args.evidence_file, "rb") as f:
        ev_bytes = f.read()

    mgr = RealOddsSnapshotManager()
    snap = mgr.import_manual_odds(
        lottery_id=args.lottery_id,
        sport=args.sport,
        odds_dict=odds_dict,
        observed_time_utc=args.observed_time,
        source_url=args.source_url,
        raw_evidence_content=ev_bytes,
        raw_evidence_filename=os.path.basename(args.evidence_file),
        is_verified_with_primary_source=args.verify
    )
    print(f"[CLI] Successfully imported odds for lottery {args.lottery_id}. Evidence class: {snap['evidence_class']}")

if __name__ == "__main__":
    main()
