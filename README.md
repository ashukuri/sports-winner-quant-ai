# ⚡ Sports WINNER Quant AI Web Dashboard

> 🌐 **Live Web Application (GitHub Pages):**  
> ### 👉 **[https://ashukuri.github.io/sports-winner-quant-ai/](https://ashukuri.github.io/sports-winner-quant-ai/)**
> 
> *PC・スマートフォンのブラウザから今すぐアクセスして、販売中試合のオッズ取得・期待値判定・AI購入判断（BET / NO BET）をご利用いただけます。*

[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Live%20Demo-brightgreen?style=for-the-badge&logo=github)](https://ashukuri.github.io/sports-winner-quant-ai/)
[![Quality Gate](https://img.shields.io/badge/Quality%20Gate-Passed%20(100%25)-blue?style=for-the-badge)]()
[![Model Version](https://img.shields.io/badge/Model%20Version-v2.0.0-purple?style=for-the-badge)]()

---

## 🌟 主な機能
1. **WINNER公式試合・オッズの自動取得**: 販売中試合のワンクリック反映 & オッズ画面コピペ自動解析パーサー
2. **AI自動購入判断 (Conservative_Value_V1)**: 理論EV > +15% かつ 的中確率 $\ge$ 8% の選択肢がある場合に「BET（1口200円）」、なければ「NO BET（見送り）」を瞬時に判定
3. **年次定期メンテナンス告知バナー**: モデルの次回推奨点検時期（毎年8〜9月）を自動カウントダウン
4. **性能劣化防止ゲート**: メンテナンス後に新モデルが旧モデルと同等以上の精度（勝敗70%以上）を維持しているか自動テスト

---

## 📖 プロジェクト概要
日本のスポーツくじ「WINNER」（サッカー1試合予想18択 / Bリーグ1試合予想16択）を対象に、過去のコード・データ生成処理を徹底監査し、架空の試合、合成倍率、未来情報を完全に排除して、実際の公式WINNER市場を観測・予測・自動精算できる信頼性の高いフォワードテスト基盤を完成させた研究プロジェクトです。


---

## 1. プロジェクト構成

```
soccer_prediction_lab/
├── README.md                           # 研究概要・実行手順・結論
├── app.py                              # Streamlit 総合クオンツ監査ダッシュボード (8大ステータス対応)
├── requirements.txt                    # 依存ライブラリ一覧
├── data/
│   ├── quarantine/                     # 【監査隔離】前回の疑わしい合成オッズ・予測ログの隔離先
│   ├── raw/                            # 公式一次資料 (楽天toto生HTML / JSON APIレスポンス)
│   ├── raw_evidence/                   # 【証拠保全】一次資料から抽出された生JSON (SHA-256付き)
│   │   └── evidence_lottery_10092.json # 第423回 千葉J vs A東京 全16択実測オッズ生データ
│   ├── odds_snapshots/                 # 実測オッズスナップショット (Type A / Type D)
│   ├── verified_fixtures.csv           # 公式ID・商品ID突合済み実在試合 (372試合)
│   ├── forward_predictions.csv         # 締切60分前固定モデル全選択肢予測ログ (196行)
│   ├── forward_transactions.csv        # 3戦略並行仮想取引元帳 (SHA-256チェーン)
│   └── settlements.csv                 # 公式結果・払戻金自動精算ログ (10円未満端数処理)
├── reports/
│   ├── root_cause_audit.md             # 【必須】架空カード・合成倍率1.43の根本原因分析報告書
│   ├── fixture_integrity_audit.md      # 【必須】公式試合日程・受入除外監査報告書
│   ├── real_odds_audit.md              # 【必須】実測オッズ・逆数合計2.0202監査報告書
│   ├── acceptance_tests.md             # 【必須】受入テスト全5件合格報告書
│   └── forward_test_readiness.md       # 【必須】フォワードテスト稼働準備状況・残存障害報告書
├── src/
│   ├── fixtures/                       # 公式試合日程受入・検証
│   │   └── fixture_manager.py          # 実在カード突合・架空カード自動除外
│   ├── odds/                           # 実測オッズ取得・整合性検査
│   │   └── odds_snapshot_manager.py    # 一次資料抽出・逆数合計計算・生証拠保全
│   ├── forward/                        # 締切60分前固定予測・3戦略判定
│   │   ├── forward_engine.py           # 固定モデル推論 & 追記専用元帳
│   │   └── paper_trader.py             # SHA-256署名・元帳チェーンエンジン
│   └── settlement/                     # 公式結果照合 & 自動精算
│       └── settlement_manager.py       # 公式約款第5条準拠（10円未満切り捨て）精算
└── tests/
    ├── test_phase4_acceptance.py       # 【必須】受入テスト (Test 1〜Test 5 全件PASS)
    └── test_quant_audit.py             # 監査ルール・Bリーグモデル単体テスト
```

---

## 2. 再現実行手順

### 環境の準備
```bash
# 仮想環境のアクティベート (Python 3.10)
source venv/bin/activate
pip install -r requirements.txt
```

### Step 1: 公式試合日程の受入・検証
```bash
python src/fixtures/fixture_manager.py
# 出力: data/verified_fixtures.csv, reports/fixture_integrity_audit.md
```

### Step 2: 実測オッズの収集・証拠保全
```bash
python src/odds/odds_snapshot_manager.py
# 出力: data/raw_evidence/, data/odds_snapshots/, reports/real_odds_audit.md
```

### Step 3: 締切60分前固定モデル予測 & 仮想取引記録
```bash
python src/forward/forward_engine.py
# 出力: data/forward_predictions.csv, data/forward_transactions.csv
```

### Step 4: 公式結果照合・自動精算
```bash
python src/settlement/settlement_manager.py
# 出力: data/settlements.csv
```

### Step 5: 受入テストの実行
```bash
python -m unittest tests/test_phase4_acceptance.py
# 実行結果: Ran 5 tests in 0.046s — OK
```

### ダッシュボードの起動
```bash
streamlit run app.py
```

---

## 3. 主要な監査結果と結論

1. **架空カード混入の根本原因 (問題A)**:
   - 前回の `src/forward/run_forward_pipeline.py` 内で、週末の第2節カード（千葉J vs 群馬 等）が公式日程やWINNER販売データ（`DLLoto`）と突合されず、手動でハードコード記述されていた。
   - 新規の `src/fixtures/fixture_manager.py` により、公式販売リスト（`DLLoto`）および商品IDが存在する実在試合のみを自動識別し、架空カードを自動拒絶する仕組みを完成。
2. **倍率逆数合計「約1.43」の真因と公式真値の発見 (問題B)**:
   - 前回のコード内で `payout_rate = 0.700`（払戻率70%）と仮定した合成オッズ数式を用いたため、数学的に $1 / 0.700 \approx 1.43$ となっていた。
   - 本監査で公式一次資料（`data/raw/detail_sample.html` 内の千葉J vs A東京 全16択実測オッズ）を復元した結果、**真の公式オッズの逆数合計は 2.0202（払戻率約49.5%、控除率約50.5%）** であり、サッカーWINNER（逆数合計 約1.99）と同一の約50%控除設計であることが証明された。
3. **合成オッズの完全排除と安全な待機**:
   - オフライン隔離環境下で取得できない販売中商品については、架空倍率を一切捏造せず `ODDS_UNAVAILABLE`（判定不能・購入額0円）として安全に待機。
4. **受入テスト全5件完全パス**:
   - 公式日程突合、逆数合計2.0202検証、不正データ自動拒絶、予測の固定保存、公式約款第5条端数処理（10円未満切り捨て）の全項目で合格。
