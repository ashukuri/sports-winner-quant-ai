#!/usr/bin/env python3
"""
src/schema/winner_schema.py
WINNER公式商品・選択肢・競技分類の共通正規化スキーマ
- Bug 1対策: 競技（Soccer / Basketball）の多角的かつ厳密な判定
- Bug 2対策: 公式選択肢番号 (1〜16 / 1〜18) を主キーとする統一マッピング
- 表記揺れ（全角波ダッシュ、ハイフン、略称）の完全正規化
"""

import re
from typing import Dict, List, Optional, Tuple, Any

# ==========================================
# 1. バスケットボール WINNER (16選択肢)
# ==========================================
BASKETBALL_CHOICE_MAP = {
    1:  {"code": "H_1-3",   "official_name": "ホーム勝利1～3点差",   "side": "HOME", "min_diff": 1,  "max_diff": 3},
    2:  {"code": "H_4-6",   "official_name": "ホーム勝利4～6点差",   "side": "HOME", "min_diff": 4,  "max_diff": 6},
    3:  {"code": "H_7-9",   "official_name": "ホーム勝利7～9点差",   "side": "HOME", "min_diff": 7,  "max_diff": 9},
    4:  {"code": "H_10-14", "official_name": "ホーム勝利10～14点差", "side": "HOME", "min_diff": 10, "max_diff": 14},
    5:  {"code": "H_15-19", "official_name": "ホーム勝利15～19点差", "side": "HOME", "min_diff": 15, "max_diff": 19},
    6:  {"code": "H_20-24", "official_name": "ホーム勝利20～24点差", "side": "HOME", "min_diff": 20, "max_diff": 24},
    7:  {"code": "H_25-29", "official_name": "ホーム勝利25～29点差", "side": "HOME", "min_diff": 25, "max_diff": 29},
    8:  {"code": "H_30+",   "official_name": "ホーム勝利30点差以上", "side": "HOME", "min_diff": 30, "max_diff": 999},
    9:  {"code": "A_1-3",   "official_name": "アウェイ勝利1～3点差",   "side": "AWAY", "min_diff": 1,  "max_diff": 3},
    10: {"code": "A_4-6",   "official_name": "アウェイ勝利4～6点差",   "side": "AWAY", "min_diff": 4,  "max_diff": 6},
    11: {"code": "A_7-9",   "official_name": "アウェイ勝利7～9点差",   "side": "AWAY", "min_diff": 7,  "max_diff": 9},
    12: {"code": "A_10-14", "official_name": "アウェイ勝利10～14点差", "side": "AWAY", "min_diff": 10, "max_diff": 14},
    13: {"code": "A_15-19", "official_name": "アウェイ勝利15～19点差", "side": "AWAY", "min_diff": 15, "max_diff": 19},
    14: {"code": "A_20-24", "official_name": "アウェイ勝利20～24点差", "side": "AWAY", "min_diff": 20, "max_diff": 24},
    15: {"code": "A_25-29", "official_name": "アウェイ勝利25～29点差", "side": "AWAY", "min_diff": 25, "max_diff": 29},
    16: {"code": "A_30+",   "official_name": "アウェイ勝利30点差以上", "side": "AWAY", "min_diff": 30, "max_diff": 999},
}

# ==========================================
# 2. サッカー WINNER (18選択肢)
# ==========================================
SOCCER_CHOICE_MAP = {
    1:  {"code": "1-0", "official_name": "1-0", "type": "HOME_WIN"},
    2:  {"code": "2-0", "official_name": "2-0", "type": "HOME_WIN"},
    3:  {"code": "2-1", "official_name": "2-1", "type": "HOME_WIN"},
    4:  {"code": "3-0", "official_name": "3-0", "type": "HOME_WIN"},
    5:  {"code": "3-1", "official_name": "3-1", "type": "HOME_WIN"},
    6:  {"code": "3-2", "official_name": "3-2", "type": "HOME_WIN"},
    7:  {"code": "other_home_win", "official_name": "その他(ホーム勝利)", "type": "HOME_WIN"},
    8:  {"code": "0-0", "official_name": "0-0", "type": "DRAW"},
    9:  {"code": "1-1", "official_name": "1-1", "type": "DRAW"},
    10: {"code": "2-2", "official_name": "2-2", "type": "DRAW"},
    11: {"code": "other_draw", "official_name": "その他(引き分け)", "type": "DRAW"},
    12: {"code": "0-1", "official_name": "0-1", "type": "AWAY_WIN"},
    13: {"code": "0-2", "official_name": "0-2", "type": "AWAY_WIN"},
    14: {"code": "1-2", "official_name": "1-2", "type": "AWAY_WIN"},
    15: {"code": "0-3", "official_name": "0-3", "type": "AWAY_WIN"},
    16: {"code": "1-3", "official_name": "1-3", "type": "AWAY_WIN"},
    17: {"code": "2-3", "official_name": "2-3", "type": "AWAY_WIN"},
    18: {"code": "other_away_win", "official_name": "その他(アウェイ勝利)", "type": "AWAY_WIN"},
}

def normalize_text(text: str) -> str:
    """全角記号や空白を正規化"""
    if not text:
        return ""
    t = text.replace("～", "-").replace("〜", "-").replace("ー", "-")
    t = t.replace("（", "(").replace("）", ")")
    t = re.sub(r'\s+', '', t)
    return t

def resolve_choice_number(sport: str, raw_name_or_code: str) -> Optional[int]:
    """
    表示名またはコードから公式 choice_number (1〜16 or 1〜18) を特定
    """
    norm = normalize_text(raw_name_or_code)
    
    if sport == "Basketball":
        for num, info in BASKETBALL_CHOICE_MAP.items():
            if norm == normalize_text(info["code"]):
                return num
            if norm == normalize_text(info["official_name"]):
                return num
            # 例: "ホーム勝利1-3" など
            alias = normalize_text(info["official_name"]).replace("点差", "").replace("以上", "+")
            if norm == alias or norm == alias + "点差":
                return num
    elif sport == "Soccer":
        for num, info in SOCCER_CHOICE_MAP.items():
            if norm == normalize_text(info["code"]):
                return num
            if norm == normalize_text(info["official_name"]):
                return num
            if "その他" in norm and ("ホーム" in norm or "home" in norm):
                if info["code"] == "other_home_win": return num
            if "その他" in norm and ("引き分け" in norm or "draw" in norm):
                if info["code"] == "other_draw": return num
            if "その他" in norm and ("アウェイ" in norm or "away" in norm):
                if info["code"] == "other_away_win": return num
    return None

def determine_sport(item: Dict[str, Any]) -> Tuple[str, str]:
    """
    Bug 1修正: 商品データから競技種別（Soccer / Basketball）を多角的に厳密判定
    Returns: (sport, reason)
    Raises: ValueError if contradictory or unresolvable
    """
    c_name = item.get("commodityName", "")
    league = item.get("gameLeagueAssortment") or item.get("gameLeagueAssortmentId", "")
    h_team = item.get("homeTeamName") or item.get("homeTeamAbbrev", "")
    a_team = item.get("awayTeamName") or item.get("awayTeamAbbrev", "")
    
    # 複合テキスト
    all_text = f"{c_name} {league} {h_team} {a_team}"
    
    # バスケットボール判定シグナル
    b_signals = []
    if any(k in all_text for k in ["B.PREMIER", "B.ONE", "B.NEXT", "B.LEAGUE", "B1", "B2", "B3", "バスケット", "basketball"]):
        b_signals.append("LEAGUE_KEYWORD")
    if any(k in all_text for k in ["レブナイズ", "ワッツ", "エクセレンス", "ゼファー", "ジェッツ", "ブレックス", "アルバルク", "ドルフィンズ", "ロボッツ", "グラウジーズ", "ベルテックス"]):
        b_signals.append("B_TEAM_NAME")
    if item.get("lotteryTypeId") == 2 and ("B." in c_name or "B.ONE" in c_name):
        b_signals.append("B_LOTTERY_TYPE")

    # サッカー判定シグナル
    s_signals = []
    if any(k in all_text for k in ["J1", "J2", "J3", "J.LEAGUE", "リーグカップ戦", "ルヴァン", "天皇杯", "サッカー", "soccer"]):
        s_signals.append("LEAGUE_KEYWORD")
    if any(k in all_text for k in ["ＦＣ", "FC", "フロンターレ", "レッズ", "グランパス", "マリノス", "エスパルス", "サンフレッチェ", "アントラーズ", "アルビレックス新潟"]):
        s_signals.append("S_TEAM_NAME")

    # 矛盾検査
    if b_signals and s_signals:
        # 例: 新潟アルビレックスBB vs アルビレックス新潟 などの混同を避ける
        if "B.ONE" in all_text or "B.PREMIER" in all_text or "B.NEXT" in all_text:
            return "Basketball", f"RESOLVED_BASKETBALL (signals: {b_signals})"
        elif "J1" in all_text or "J2" in all_text or "J3" in all_text or "リーグカップ戦" in all_text:
            return "Soccer", f"RESOLVED_SOCCER (signals: {s_signals})"
        else:
            raise ValueError(f"CONTRADICTORY_SPORT_SIGNALS: Basketball={b_signals}, Soccer={s_signals} in '{all_text}'")

    if b_signals:
        return "Basketball", f"IDENTIFIED_BASKETBALL ({b_signals})"
    if s_signals:
        return "Soccer", f"IDENTIFIED_SOCCER ({s_signals})"

    raise ValueError(f"UNRESOLVABLE_SPORT: Cannot determine sport for '{all_text}'")
