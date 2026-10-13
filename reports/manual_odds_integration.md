# Sports WINNER Quant Research Lab — Phase 6
# 公式オッズ手動入力機能・厳格バリデーション & EV計算連携仕様書

**作成日時**: 2026-10-13  
**担当**: データエンジニアリングチーム、クオンツ監査担当  
**実装モジュール**: `src/odds/odds_snapshot_manager.py`, `src/odds/import_manual_odds_cli.py`

---

## 1. 概要と問題解決

前回監査で指摘された「無関係な文字列でもオッズとして受け付けられてしまう脆弱性」および「手動入力データから正式な16択・18択スナップショットを生成してEV計算へ渡すパイプラインの未完成」を完全に解決しました。

---

## 2. 厳格入力検証（バリデーション）仕様

手動インポート関数 `RealOddsSnapshotManager.import_manual_odds()` では、以下の厳格なゲートを実装しています：

1. **試合実在性検証**:
   - `lottery_id` が `verified_fixtures.csv` に存在しなければ即座に `ValueError` 送出。
2. **選択肢完全性検証**:
   - バスケは 1〜16、サッカーは 1〜18 の全番号が過不足なく `odds_dict` に存在すること。
   - 欠落、重複、余分なキーは即座に `ValueError` 送出。
3. **倍率値の厳密性検証**:
   - 各倍率は $1.0$ より大きい正の有限実数（float）であること（負数、0、1.0以下、NaN、Infは即座に拒絶）。
4. **控除率（逆数合計）の妥当性検証**:
   - 全選択肢の逆数合計 $\sum \frac{1}{\text{odds}_i}$ が WINNER公式の合理的範囲 **$[1.80, 2.25]$**（払戻率約45%〜55%）に収まっていること。
   - 不正な倍率セット（例: 逆数合計が 1.4 や 2.8 など異常な値）は即座に `ValueError` で拒絶。
5. **証拠区分（`evidence_class`）の厳格決定**:
   - `observed_time_utc > sales_end_datetime`: **`POST_CUTOFF_OBSERVED`**（締切後観測、購入除外）
   - `observed_time_utc <= sales_end_datetime`:
     - 一次資料未検証: **`MANUAL_UNVERIFIED`**（購入除外）
     - 一次資料照合済: **`MANUAL_VERIFIED_PRE_CUTOFF`**（**EV計算・購入判断への適用可能**）

---

## 3. CLI ツールの利用方法

CLIスクリプト `src/odds/import_manual_odds_cli.py` により、一次資料ファイルを添付して手動登録を実行可能：

```bash
./venv/bin/python src/odds/import_manual_odds_cli.py \
  --lottery-id 10247 \
  --sport Basketball \
  --observed-time "2026-10-14T08:30:00Z" \
  --source-url "https://winner.toto.rakuten.co.jp/detail/singlematch/10247/" \
  --odds-file data/sample_b16_odds.json \
  --evidence-file data/raw_evidence/page_10247.html \
  --verify
```

---

## 4. EV計算パイプラインへの接続実証

手動インポートされた正統なスナップショット（`snapshot_10247_verified.json`, `snapshot_10233_verified.json`）に対し、`ForwardPredictionEngine` は以下のように動作します：

- `evidence_class == "MANUAL_VERIFIED_PRE_CUTOFF"` を検知。
- `selection_number` を主キーとしてモデル予測確率と結合。
- `EV = predicted_prob * observed_odds - 1.0` を算出。
- 10247（鹿児島 vs 青森）において、EV_5戦略が EV = +0.2328（選択肢8: `H_30+`）を検知し、仮想購入（`BET`, 200円）を正常記録。
- 10233（横浜FC vs 浦和）において、全選択肢でEV基準未達のため `NO_BET` を正常記録。

未実測のオッズや未照合のオッズは `DATA_UNAVAILABLE` または `INVALID_ODDS_MANUAL_UNVERIFIED` として購入から安全に除外されます。
