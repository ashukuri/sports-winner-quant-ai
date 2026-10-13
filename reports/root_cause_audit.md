# 根本原因分析・監査報告書 (Root Cause Audit)
## 前回のデータ生成処理・対戦カード・倍率計算の徹底監査

**監査実施日時**: 2026年10月13日 22:25:00 JST  
**監査対象**: `src/forward/run_forward_pipeline.py`, `reports/predictions.csv`, `reports/paper_transactions.csv`, `data/odds_snapshots/`  
**監査ステータス**: 完了（すべての生成元および不整合要因を100%特定）

---

## 1. 既存データ生成元（項目1〜10）の完全特定

前回の `predictions.csv` および `data/odds_snapshots/` を出力した処理について、該当ソースコードのファイル名、関数名、行番号、および実体を以下のように特定した。

| 監査項目 | 特定結果・実体 | 該当ソースファイル | 該当関数 / 行番号 | 監査評価 |
|:---|:---|:---|:---|:---:|
| **1. 試合一覧を生成したコード** | モジュールレベルで定義された固定辞書配列 `TARGET_MATCHES` | `src/forward/run_forward_pipeline.py` | `TARGET_MATCHES` (L40–L160) | **不適格（手動定義）** |
| **2. チーム名を取得したデータソース** | サッカー・B.ONE（10233〜10248）は `data/raw/` のJSONから転記。B.PREMIER（20001〜20003）は公式日程に存在しない手動創作 | `src/forward/run_forward_pipeline.py` | `TARGET_MATCHES` (L121–L160) | **重大な欠陥（架空カード混入）** |
| **3. 日付と時刻の設定方法** | `"2026-10-16T10:05:00Z"` などのハードコード文字列を手動設定 | `src/forward/run_forward_pipeline.py` | `TARGET_MATCHES` 各要素内 | **不適格（固定文字列）** |
| **4. 公式試合IDの取得方法** | `"BSK_20261016_20001"` などの非公式ID文字列を任意に付与 | `src/forward/run_forward_pipeline.py` | `TARGET_MATCHES['match_id']` | **不適格（推測ID）** |
| **5. 倍率を取得したコード** | 数式により合成オッズを算出するシミュレータ関数 | `src/forward/run_forward_pipeline.py` | `generate_soccer_odds()` (L179)<br>`generate_basketball_odds()` (L194) | **重大な欠陥（数式合成）** |
| **6. 倍率の取得URL** | 外部URLやAPIアクセスは一切なし（`None`） | なし | 該当処理なし | **実測値なし** |
| **7. 倍率の性質（実測/計算/固定）** | **計算値（合成倍率・Type C）**。実測値（Type A）ではない | `src/forward/run_forward_pipeline.py` | `odds = payout_rate / np.clip(...)` | **Type C（実測偽証）** |
| **8. 予測時刻の生成方法** | スクリプト実行時のローカル現在時刻 `datetime.now().isoformat()` | `src/forward/run_forward_pipeline.py` | `main()` (L255) | **販売締切60分前ではない** |
| **9. 予測確率の生成モデル** | サッカー: `DixonColesModel`<br>バスケ: 簡易Student-t積分関数 `compute_basketball_ensemble_probs()` | `src/models/dixon_coles.py`<br>`src/forward/run_forward_pipeline.py` | `predict_winner_18_proba()`<br>`compute_basketball_ensemble_probs()` (L207) | 確率自体は数理的だがモデルが一部簡略化 |
| **10. CSV出力までのデータ処理** | ループ内で辞書を作成し `pd.DataFrame` に変換して `to_csv()` | `src/forward/run_forward_pipeline.py` | `main()` (L280–L350) | 合成データがCSV化された |

---

## 2. 重大な問題の解明と数理的真因

### 問題A：実在しない対戦カードの混入原因
- `TARGET_MATCHES` に記載されていた以下の3試合：
  - `BSK_20261016_20001`: 千葉ジェッツ vs 群馬クレインサンダーズ (2026-10-16)
  - `BSK_20261017_20002`: アルバルク東京 vs 三遠ネオフェニックス (2026-10-17)
  - `BSK_20261018_20003`: 宇都宮ブレックス vs 琉球ゴールデンキングス (2026-10-18)
- **真因**: 公式WINNER販売リスト（`DLLoto`）およびBリーグ公式日程をスクレイピング・照合したものではなく、コード作成時に週末の第2節カードとして開発者が**手動で仮定（ハードコード）した架空の対戦カード**であった。
- 公式APIレスポンス `winner_basketball_json.json` の `DLLoto` に実際に登録されていた直近販売対象試合は、`10247`（鹿児島 vs 青森）および `10248`（福岡 vs 横浜EX）のみであった。

### 問題B：BリーグWINNER倍率の逆数合計が「約1.43」となった数理的真因
- 前回のコード `src/forward/run_forward_pipeline.py` L194–205:
  ```python
  def generate_basketball_odds(probs):
      payout_rate = 0.700  # <- 払戻率70%（控除率30%）と仮定
      prior = 1.0 / len(probs)
      market_probs = probs * 0.85 + prior * 0.15
      odds = payout_rate / np.clip(market_probs, 0.005, 0.95)
      odds = np.round(odds, 1)
      return np.maximum(odds, 1.1)
  ```
- **数学的帰結**:
  $$\sum_{i=1}^{16} \frac{1}{\text{odds}_i} \approx \sum_{i=1}^{16} \frac{\text{market\_probs}_i}{\text{payout\_rate}} = \frac{1}{\text{payout\_rate}} \sum_{i=1}^{16} \text{market\_probs}_i = \frac{1}{0.700} = 1.42857 \approx 1.43$$
- 一方、サッカー側では `payout_rate = 0.502` と設定されていたため：
  $$\sum_{i=1}^{18} \frac{1}{\text{odds}_i} \approx \frac{1}{0.502} = 1.992 \approx 1.99$$
- **公式実測データとの対比**:
  - 本監査において、公式一次資料 `data/raw/detail_sample.html` 内に埋め込まれていた公式WINNER実データ（第423回 千葉J vs A東京、全16選択肢実測オッズ）を解析したところ、**真の公式オッズの逆数合計は 2.0202（払戻率 約49.5%、控除率 約50.5%）** であることが判明した。
  - すなわち、**BリーグWINNERの払戻率もサッカーWINNERと同様に約50%で設計されており、70%という仮定自体が誤りであった**。
  - 逆数合計が約1.43となったのは、公式市場の性質ではなく、**開発者が埋め込んだ合成関数のパラメータ `payout_rate = 0.700` に起因する純粋な人工的産物**であった。

---

## 3. 隔離措置（Quarantine）の記録

疑わしい既存データを破棄せず、監査証跡として保存するため、以下のファイルを `data/quarantine/` に移動・隔離した。

- `data/quarantine/predictions.csv` (合成オッズによる事前予測CSV)
- `data/quarantine/paper_transactions.csv` (合成オッズに基づく取引CSV)
- `data/quarantine/odds_snapshots/` (合成オッズスナップショット 9件)
- `data/quarantine/forward/` (`locked_predictions.jsonl`, `forward_ledger.csv`)

現行の `data/odds_snapshots/` および `reports/` からはこれらを完全に排除し、実測証拠のみを受け入れるクリーンな環境に修復した。
