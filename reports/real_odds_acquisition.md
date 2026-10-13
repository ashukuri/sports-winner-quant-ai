# Sports WINNER Quant Research Lab — Phase 5
# 実測オッズ取得状況・販売中試合監査および手動インポート機能仕様書

**作成日時**: 2026-10-13  
**担当**: データエンジニアリングチーム、クオンツ監査担当  
**対象システム**: `src/odds/odds_snapshot_manager.py`, `data/odds_snapshots/`

---

## 1. 実測オッズ取得の現状と監査方針

Sports WINNER Quant Research Lab Phase 5 では、「**未取得の実測オッズを合成倍率や架空データで補填することを厳禁とする**」という鉄則を遵守しています。

本研究環境はセキュアなローカルサンドボックス（外部ネットワーク遮断）環境下で稼働しているため、販売中のリアルタイムWINNERオッズ取得APIへの動的HTTPアクセスは制限されています。
この制約に対し、本システムは「オッズが未取得である」という事実を正確かつ誠実に表現し、`ODDS_UNAVAILABLE` / `DATA_UNAVAILABLE` として意思決定および仮想購入を自動停止する安全設計を採用しています。

---

## 2. 販売中10試合のオッズ観測ステータス

現在、公式くじシステムにおいて販売中として特定されている10試合（サッカー8試合、バスケットボール2試合）の観測ステータスは以下の通りです。

| くじID | 競技種別 | 大会名 | 対戦カード | 販売締切日時 (UTC) | オッズステータス | 証拠区分 | 意思決定 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **10233** | Soccer | リーグカップ戦 | 横浜FC vs 浦和レッズ | 2026-10-14 09:20 | `ODDS_UNAVAILABLE` | `UNAVAILABLE` | `DATA_UNAVAILABLE` |
| **10234** | Soccer | リーグカップ戦 | 水戸ホーリーホック vs ＦＣ東京 | 2026-10-14 09:50 | `ODDS_UNAVAILABLE` | `UNAVAILABLE` | `DATA_UNAVAILABLE` |
| **10235** | Soccer | リーグカップ戦 | 鹿島アントラーズ vs 川崎フロンターレ | 2026-10-14 09:50 | `ODDS_UNAVAILABLE` | `UNAVAILABLE` | `DATA_UNAVAILABLE` |
| **10236** | Soccer | リーグカップ戦 | 柏レイソル vs ガンバ大阪 | 2026-10-14 09:50 | `ODDS_UNAVAILABLE` | `UNAVAILABLE` | `DATA_UNAVAILABLE` |
| **10237** | Soccer | リーグカップ戦 | 東京ヴェルディ vs アルビレックス新潟 | 2026-10-14 09:50 | `ODDS_UNAVAILABLE` | `UNAVAILABLE` | `DATA_UNAVAILABLE` |
| **10238** | Soccer | リーグカップ戦 | 湘南ベルマーレ vs 名古屋グランパス | 2026-10-14 09:50 | `ODDS_UNAVAILABLE` | `UNAVAILABLE` | `DATA_UNAVAILABLE` |
| **10239** | Soccer | リーグカップ戦 | サンフレッチェ広島 vs ヴィッセル神戸 | 2026-10-14 09:50 | `ODDS_UNAVAILABLE` | `UNAVAILABLE` | `DATA_UNAVAILABLE` |
| **10240** | Soccer | リーグカップ戦 | アビスパ福岡 vs セレッソ大阪 | 2026-10-14 09:50 | `ODDS_UNAVAILABLE` | `UNAVAILABLE` | `DATA_UNAVAILABLE` |
| **10247** | Basketball | B.ONE | 鹿児島レブナイズ vs 青森ワッツ | 2026-10-14 09:55 | `ODDS_UNAVAILABLE` | `UNAVAILABLE` | `DATA_UNAVAILABLE` |
| **10248** | Basketball | B.ONE | ライジングゼファー福岡 vs 横浜エクセレンス | 2026-10-14 09:55 | `ODDS_UNAVAILABLE` | `UNAVAILABLE` | `DATA_UNAVAILABLE` |

### 監査所見
- すべての販売中試合において、オッズが存在しないことによる `DATA_UNAVAILABLE` が正常に出力され、架空オッズによる注文（仮想購入）は1件も発生していません（購入額0円）。
- 期待値（EV）の計算も停止（None）しており、データの欠損がシステムの暴走を招かないことが実証されています。

---

## 3. 過去試合（10092 千葉J vs A東京）の再監査と分類

第423回 B.PREMIER 千葉ジェッツ vs アルバルク東京（lottery_id: 10092）については、一次証拠ファイル `evidence_lottery_10092.json`（全16選択肢オッズおよび確定払戻金1,080円を記録）が存在します。

しかし、前述のBug 3監査により、本ファイルは販売締切（2026-10-02 09:55 UTC）より後の 2026-10-03 00:49 UTC に取得されたアーカイブ値であることが判明しました。
そのため、本システムではこれを以下のように再分類・隔離しました：

- **ファイル**: `data/odds_snapshots/snapshot_10092_verified.json`
- **証拠区分**: `POST_CUTOFF_OBSERVED`（締切後観測オッズ）
- **フォワードテスト判定**: `INVALID_ODDS_POST_CUTOFF_OBSERVED`
- **購入除外**: 事前購入判断への流用を完全禁止、仮想購入額 0円

---

## 4. 実測オッズ手動インポート機能の仕様と動作実証

外部ネットワークに接続可能な端末でWINNER公式サイト（楽天toto、スポーツくじ公式サイト等）から取得した事前実測オッズを、安全かつ改ざん不能な形式でフォワードテスト基盤に取り込むための「手動インポートツール」を実装しました。

### 4.1 CLI インポートコマンド
```bash
./venv/bin/python -c '
from src.odds.odds_snapshot_manager import RealOddsSnapshotManager

# 例: 鹿児島 vs 青森 (10247) の事前実測オッズを手動登録
# odds_dict は selection_number (1〜16) をキーとする実測オッズ
mgr = RealOddsSnapshotManager()
mgr.import_manual_odds(
    lottery_id=10247,
    sport="Basketball",
    odds_dict={1: 7.2, 2: 6.5, 3: 8.1, 4: 12.0, 5: 18.5, 6: 25.0, 7: 35.0, 8: 45.0,
               9: 5.8, 10: 4.9, 11: 6.2, 12: 9.8, 13: 15.0, 14: 22.0, 15: 30.0, 16: 40.0},
    observed_time_utc="2026-10-14T08:30:00Z",
    source_url="https://tobaccoseller.rakuten.co.jp/winner/basketball/10247"
)
'
```

### 4.2 インポート時の暗号学的監査処理
1. **選択肢完全性検証**: バスケ16択、サッカー18択の全選択肢が欠損なく揃っているかを検証。
2. **逆数合計（控除率）検証**: オッズ逆数合計が約 2.02（払戻率約49.5%）の合理的範囲（1.95〜2.10）に収まっているかを自動判定。
3. **証拠区分自動判定**: 観測時刻（`observed_time_utc`）が販売締切時刻前であれば `PRE_CUTOFF_OBSERVED`、締切後であれば `POST_CUTOFF_OBSERVED` を自動付与。
4. **SHA-256ハッシュ刻印**: 生成されたスナップショットJSONのSHA-256ハッシュを計算し、台帳追記時に照合。

---

## 5. 結論

本システムは、合成倍率の排除と未取得オッズの明示的管理を達成しており、実際の試合前オッズが入手された際には、手動インポートまたはAPI連携を通じて即座に正統なフォワードテスト評価を実施可能な状態に整備されています。
