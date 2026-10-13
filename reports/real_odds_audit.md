# 実測オッズ監査・証拠保全報告書 (Real Odds Audit Phase 5)

**作成日時**: 2026-10-13 22:44:58 JST  
**監査対象**: 公式一次資料オッズ、証拠分類、手動インポート仕様  
**Bug 3修正**: 取得時刻と販売締切時刻の厳格照合による再分類

---

## 1. 証拠区分定義 (Evidence Classification)

| 区分コード | 定義・要件 | 購入判断への利用 |
|:---|:---|:---:|
| **PRE_CUTOFF_OBSERVED** | 販売締切前に実際に取得した一次資料付き実測倍率 | **利用可能 (唯一の正当根拠)** |
| **POST_CUTOFF_OBSERVED** | 販売締切後に取得された表示倍率（過去アーカイブ） | **事後精算・参考用のみ（購入判断禁止）** |
| **OFFICIAL_FINAL_PAYOUT** | 公式確定当せん金・払戻金 | 事後精算のみ |
| **SYNTHETIC** | 数式やモデルから推計した倍率 | **利用禁止 (実証算入不可)** |
| **UNVERIFIED** | 一次資料や取得時刻が未検証のデータ | 利用禁止 |
| **UNAVAILABLE** | 取得できなかった状態 | **判定不能 (購入見送りとは区別)** |

---

## 2. 第423回 千葉J vs A東京 (10092) の再分類結果 (Bug 3修正)

- **公式販売締切**: `2026-10-02T09:55:00.000000Z`
- **証拠取得時刻**: `2026-10-13T13:23:00Z`
- **再分類結果**: **`POST_CUTOFF_OBSERVED`**
- **事前購入判断への適用可否**: **`False (利用禁止・事後検証用)`**

> [!CAUTION]
> **Bug 3の是正**: 前回の監査では締切後データ（10092）が誤って購入前実測とみなされていましたが、取得時刻が締切後であるため `POST_CUTOFF_OBSERVED` に厳密に格下げ・再分類されました。

---

## 3. 現在販売中試合の状況

| くじID | 競技 | 対戦カード | 証拠区分 | 判定処理 |
|:---:|:---:|:---|:---:|:---:|
| `10233` | Soccer | 横浜ＦＣ vs 浦和レッズ | `UNAVAILABLE` | **架空補完を排除 (DATA_UNAVAILABLE)** |
| `10234` | Soccer | 水戸ホーリーホック vs ＦＣ東京 | `UNAVAILABLE` | **架空補完を排除 (DATA_UNAVAILABLE)** |
| `10235` | Soccer | 横浜Ｆ・マリノス vs 清水エスパルス | `UNAVAILABLE` | **架空補完を排除 (DATA_UNAVAILABLE)** |
| `10236` | Soccer | 松本山雅ＦＣ vs サンフレッチェ広島 | `UNAVAILABLE` | **架空補完を排除 (DATA_UNAVAILABLE)** |
| `10237` | Soccer | ジュビロ磐田 vs 川崎フロンターレ | `UNAVAILABLE` | **架空補完を排除 (DATA_UNAVAILABLE)** |
| `10238` | Soccer | 名古屋グランパス vs ファジアーノ岡山 | `UNAVAILABLE` | **架空補完を排除 (DATA_UNAVAILABLE)** |
| `10239` | Soccer | ガイナーレ鳥取 vs セレッソ大阪 | `UNAVAILABLE` | **架空補完を排除 (DATA_UNAVAILABLE)** |
| `10240` | Soccer | サガン鳥栖 vs アビスパ福岡 | `UNAVAILABLE` | **架空補完を排除 (DATA_UNAVAILABLE)** |
| `10247` | Basketball | 鹿児島レブナイズ vs 青森ワッツ | `UNAVAILABLE` | **架空補完を排除 (DATA_UNAVAILABLE)** |
| `10248` | Basketball | ライジングゼファー福岡 vs 横浜エクセレンス | `UNAVAILABLE` | **架空補完を排除 (DATA_UNAVAILABLE)** |

---

## 4. 手動インポート機能の整備
ネットワーク隔離環境に対応するため、一次資料ファイルと取得時刻UTCを入力として `PRE_CUTOFF_OBSERVED` を安全に受入・検証する `import_manual_odds` メソッドを実装しました。
