#!/usr/bin/env python3
"""
scripts/fetch_real_official_odds.py
楽天toto公式サイトから現在販売中および直近の全WINNER試合と、
正真正銘の「公式リアルタイムオッズ」を一括自動スクレイピングして
docs/fixtures_preset.json および docs/fixtures_preset.js に格納するスクリプト。
"""

import os
import sys
import json
import time
import re
import urllib.request
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR = os.path.join(BASE_DIR, "docs")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_html(url, timeout=12):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")

def extract_json_array(text, key_name):
    """
    scriptタグ内の key_name:[...] をブラケットの深さカウントで安全にパース
    """
    for script in re.findall(r'<script[^>]*>(.*?)</script>', text, re.DOTALL):
        idx = script.find(f'"{key_name}":')
        if idx == -1:
            idx = script.find(f'{key_name}:')
            if idx == -1:
                continue
            start_bracket = idx + len(f'{key_name}:')
        else:
            start_bracket = idx + len(f'"{key_name}":')
        
        while start_bracket < len(script) and script[start_bracket].isspace():
            start_bracket += 1
        if start_bracket >= len(script) or script[start_bracket] != '[':
            continue
            
        depth = 0
        end_bracket = -1
        for i in range(start_bracket, len(script)):
            c = script[i]
            if c == '[':
                depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0:
                    end_bracket = i + 1
                    break
        if end_bracket != -1:
            try:
                return json.loads(script[start_bracket:end_bracket])
            except Exception as e:
                pass
    return []

def fetch_all_official_matches():
    """
    楽天toto公式からサッカー・バスケの全試合カタログを取得
    """
    print("[1/3] 楽天toto公式サイトから試合カタログを取得中...")
    matches_dict = {}

    # 1. トップページから todayGameList を取得
    try:
        top_html = fetch_html("https://winner.toto.rakuten.co.jp/")
        today_games = extract_json_array(top_html, "todayGameList")
        print(f"  - トップページ (todayGameList): {len(today_games)} 試合発見")
        for g in today_games:
            lid = g.get("lotteryId")
            if lid:
                matches_dict[lid] = g
    except Exception as e:
        print(f"  ⚠️ トップページ取得エラー: {e}")

    # 2. サッカー全試合 (/singlematch/soccer/)
    try:
        soccer_html = fetch_html("https://winner.toto.rakuten.co.jp/singlematch/soccer/")
        soccer_lots = extract_json_array(soccer_html, "lotteries")
        print(f"  - サッカー一覧ページ: {len(soccer_lots)} 試合発見")
        for g in soccer_lots:
            lid = g.get("lotteryId")
            if lid and lid not in matches_dict:
                matches_dict[lid] = g
    except Exception as e:
        print(f"  ⚠️ サッカー一覧取得エラー: {e}")

    # 3. バスケ全試合 (/singlematch/basketball/)
    try:
        basket_html = fetch_html("https://winner.toto.rakuten.co.jp/singlematch/basketball/")
        basket_lots = extract_json_array(basket_html, "lotteries")
        print(f"  - バスケ一覧ページ: {len(basket_lots)} 試合発見")
        for g in basket_lots:
            lid = g.get("lotteryId")
            if lid and lid not in matches_dict:
                matches_dict[lid] = g
    except Exception as e:
        print(f"  ⚠️ バスケ一覧取得エラー: {e}")

    print(f"  => 重複除外後の合計試合数: {len(matches_dict)} 試合")
    return list(matches_dict.values())

def fetch_single_detail_odds(match, max_retries=3):
    """
    各試合の公式詳細ページから selections (オッズ) をスクレイピング
    """
    lid = match.get("lotteryId")
    hold = match.get("holdCountId")
    comm = match.get("commodityId")

    league_id = str(match.get("gameLeagueAssortmentId", ""))
    league_name = str(match.get("gameLeagueAssortment", ""))
    is_basket = any(k in league_id or k in league_name for k in ["B.", "B1", "B2", "B3", "BO", "BP", "BN", "B "]) or "バスケ" in str(match.get("commodityName", ""))
    sport_path = "basketball" if is_basket else "soccer"
    sport_label = "Basketball" if is_basket else "Soccer"

    if not hold or not comm:
        return lid, sport_label, {}, "Missing holdCountId/commodityId"

    detail_url = f"https://winner.toto.rakuten.co.jp/singlematch/{sport_path}/detail?holdCountId={hold}&commodityId={comm}&mode=detail"

    last_error = ""
    for attempt in range(max_retries):
        try:
            html = fetch_html(detail_url, timeout=12)
            m = re.search(r'"selections"\s*:\s*(\[[^\]]+\])', html)
            if m:
                sel = json.loads(m.group(1))
                odds_dict = {}
                for s in sel:
                    num_str = str(s.get("selectionNumber"))
                    raw_odds = s.get("odds")
                    if raw_odds is not None:
                        try:
                            odds_dict[num_str] = float(raw_odds)
                        except (ValueError, TypeError):
                            pass
                    else:
                        odds_dict[num_str] = None
                return lid, sport_label, odds_dict, detail_url
            else:
                last_error = "No selections in HTML"
        except Exception as e:
            last_error = str(e)
            time.sleep(0.5 * (attempt + 1))
            
    return lid, sport_label, {}, last_error


def main():
    raw_matches = fetch_all_official_matches()
    if not raw_matches:
        print("❌ 試合情報の取得に失敗しました。")
        sys.exit(1)

    # 既存の preset があればロード（フォールバック用）
    existing_preset = {}
    preset_json_path = os.path.join(DOCS_DIR, "fixtures_preset.json")
    if os.path.exists(preset_json_path):
        try:
            with open(preset_json_path, "r", encoding="utf-8") as f:
                for item in json.load(f):
                    existing_preset[item.get("lottery_id")] = item
        except Exception:
            pass

    # 販売中・直近開催の試合を優先ソート
    now_iso = datetime.now(timezone.utc).isoformat()
    print(f"\n[2/3] 全 {len(raw_matches)} 試合の公式詳細ページからリアルタイムオッズを並列取得中...")

    # 販売中と販売終了を分ける
    in_sale = [m for m in raw_matches if (m.get("salesEndDatetime") or "") > now_iso]
    ended = [m for m in raw_matches if (m.get("salesEndDatetime") or "") <= now_iso]
    
    # 締切時刻順にソート (直近締切が先頭)
    in_sale.sort(key=lambda x: x.get("salesEndDatetime", ""))
    ended.sort(key=lambda x: x.get("salesEndDatetime", ""), reverse=True)
    target_matches = in_sale + ended

    print(f"  - 販売中: {len(in_sale)} 試合")
    print(f"  - 締切済: {len(ended)} 試合")
    print(f"  - 取得対象: 全 {len(target_matches)} 試合")

    # 並列フェッチ実行 (max_workers=6)
    t0 = time.time()
    results = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        for lid, sport_label, odds_dict, info in executor.map(fetch_single_detail_odds, target_matches):
            results[lid] = (sport_label, odds_dict, info)

    # 未取得の販売中試合があれば、少し休止してリトライ
    missing_in_sale = [m for m in in_sale if len([v for v in results.get(m.get("lotteryId"), ("", {}))[1].values() if v is not None]) < 14]
    if missing_in_sale:
        print(f"  - 未取得の販売中 {len(missing_in_sale)} 試合を再取得中...")
        time.sleep(1.0)
        with ThreadPoolExecutor(max_workers=4) as executor:
            for lid, sport_label, odds_dict, info in executor.map(fetch_single_detail_odds, missing_in_sale):
                if len([v for v in odds_dict.values() if v is not None]) >= 14:
                    results[lid] = (sport_label, odds_dict, info)

    elapsed = time.time() - t0
    success_count = sum(1 for _, odds, _ in results.values() if len([v for v in odds.values() if v is not None]) >= 14)
    print(f"  => オッズ取得完了: {elapsed:.2f}秒 (公式リアルタイムオッズ取得成功: {success_count}/{len(target_matches)} 試合)")


    # プリセットデータ構築
    final_fixtures = []
    for m in target_matches:
        lid = m.get("lotteryId")
        sport_label, live_odds, info = results.get(lid, ("Soccer", {}, ""))

        # チーム名と商品名
        home_name = m.get("homeTeamName") or m.get("homeTeamAbbrev") or "ホーム"
        away_name = m.get("awayTeamName") or m.get("awayTeamAbbrev") or "アウェイ"
        commodity_name = m.get("commodityName") or f"{home_name} vs {away_name}"
        game_date = (m.get("gameDate") or "")[:10]
        deadline = m.get("salesEndDatetime")
        hold_count_id = m.get("holdCountId")
        commodity_id = m.get("commodityId")

        # オッズの確定 (主要な買い目に公式投票が入っていれば公式リアルタイムオッズを採用)
        valid_live_odds = {k: v for k, v in live_odds.items() if v is not None}
        is_official = False

        if len(valid_live_odds) >= 5:
            # 公式実測オッズを使用 (未投票の選択肢は null またはフォールバック)
            final_odds = {}
            total_choices = 16 if sport_label == "Basketball" else 18
            for i in range(1, total_choices + 1):
                key = str(i)
                if key in live_odds and live_odds[key] is not None:
                    final_odds[key] = live_odds[key]
                else:
                    # 未投票選択肢: 99.0倍 (投票ゼロのため高倍率)
                    final_odds[key] = 99.0
            is_official = True
        elif lid in existing_preset and existing_preset[lid].get("odds"):
            # 既存プリセットからフォールバック
            final_odds = existing_preset[lid]["odds"]
            is_official = existing_preset[lid].get("is_official_odds", False)
        else:
            # 最小フォールバック
            count = 16 if sport_label == "Basketball" else 18
            final_odds = {str(i): round(6.0 + (i % 5) * 2.5, 1) for i in range(1, count + 1)}
            is_official = False


        fixture_obj = {
            "lottery_id": lid,
            "sport": sport_label,
            "commodity_name": commodity_name,
            "home_team": home_name,
            "away_team": away_name,
            "game_date": game_date,
            "deadline": deadline,
            "hold_count_id": hold_count_id,
            "commodity_id": commodity_id,
            "is_official_odds": is_official,
            "odds": final_odds
        }
        final_fixtures.append(fixture_obj)

    # 3. ファイル書き出し
    print("\n[3/3] docs/fixtures_preset.json および docs/fixtures_preset.js に書き込み中...")
    with open(preset_json_path, "w", encoding="utf-8") as f:
        json.dump(final_fixtures, f, ensure_ascii=False, indent=2)

    preset_js_path = os.path.join(DOCS_DIR, "fixtures_preset.js")
    with open(preset_js_path, "w", encoding="utf-8") as f:
        f.write("// WINNER公式試合＆最新公式リアルタイムオッズ・プリセットデータ\n")
        f.write(f"// 自動生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("window.FIXTURES_PRESET = window.WINNER_FIXTURES = ")
        json.dump(final_fixtures, f, ensure_ascii=False, indent=2)
        f.write(";\n")


    print(f"✅ 書き込み完了: 全 {len(final_fixtures)} 試合を格納")
    print(f"  - 公式リアルタイムオッズ取得済: {sum(1 for f in final_fixtures if f['is_official_odds'])} 試合")

    # サンプル表示
    print("\n--- サンプル確認 ---")
    for sample in final_fixtures[:3]:
        print(f"くじID: {sample['lottery_id']} ({sample['sport']}) | {sample['commodity_name']}")
        print(f"  締切: {sample['deadline']} | hold: {sample['hold_count_id']}, comm: {sample['commodity_id']}")
        print(f"  公式オッズフラグ: {sample['is_official_odds']}")
        sample_odds = [f"{k}: {v}倍" for k, v in list(sample['odds'].items())[:5]]
        print(f"  オッズ例 (先頭5選択肢): {', '.join(sample_odds)}")

if __name__ == "__main__":
    main()
