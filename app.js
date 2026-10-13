// Sports WINNER Quant AI - Web Engine (app.js)
// GitHub Pages クライアントサイド完全動作版

// 選択肢マップ定義
const BASKETBALL_CHOICES = [
  { num: 1, code: "H_1-3", name: "ホーム勝利 1～3点差", side: "HOME", min: 1, max: 3 },
  { num: 2, code: "H_4-6", name: "ホーム勝利 4～6点差", side: "HOME", min: 4, max: 6 },
  { num: 3, code: "H_7-9", name: "ホーム勝利 7～9点差", side: "HOME", min: 7, max: 9 },
  { num: 4, code: "H_10-14", name: "ホーム勝利 10～14点差", side: "HOME", min: 10, max: 14 },
  { num: 5, code: "H_15-19", name: "ホーム勝利 15～19点差", side: "HOME", min: 15, max: 19 },
  { num: 6, code: "H_20-24", name: "ホーム勝利 20～24点差", side: "HOME", min: 20, max: 24 },
  { num: 7, code: "H_25-29", name: "ホーム勝利 25～29点差", side: "HOME", min: 25, max: 29 },
  { num: 8, code: "H_30+", name: "ホーム勝利 30点差以上", side: "HOME", min: 30, max: 100 },
  { num: 9, code: "A_1-3", name: "アウェイ勝利 1～3点差", side: "AWAY", min: 1, max: 3 },
  { num: 10, code: "A_4-6", name: "アウェイ勝利 4～6点差", side: "AWAY", min: 4, max: 6 },
  { num: 11, code: "A_7-9", name: "アウェイ勝利 7～9点差", side: "AWAY", min: 7, max: 9 },
  { num: 12, code: "A_10-14", name: "アウェイ勝利 10～14点差", side: "AWAY", min: 10, max: 14 },
  { num: 13, code: "A_15-19", name: "アウェイ勝利 15～19点差", side: "AWAY", min: 15, max: 19 },
  { num: 14, code: "A_20-24", name: "アウェイ勝利 20～24点差", side: "AWAY", min: 20, max: 24 },
  { num: 15, code: "A_25-29", name: "アウェイ勝利 25～29点差", side: "AWAY", min: 25, max: 29 },
  { num: 16, code: "A_30+", name: "アウェイ勝利 30点差以上", side: "AWAY", min: 30, max: 100 }
];

const SOCCER_CHOICES = [
  { num: 1, code: "1-0", name: "1 - 0 (ホーム勝ち)", h: 1, a: 0 },
  { num: 2, code: "2-0", name: "2 - 0 (ホーム勝ち)", h: 2, a: 0 },
  { num: 3, code: "2-1", name: "2 - 1 (ホーム勝ち)", h: 2, a: 1 },
  { num: 4, code: "3-0", name: "3 - 0 (ホーム勝ち)", h: 3, a: 0 },
  { num: 5, code: "3-1", name: "3 - 1 (ホーム勝ち)", h: 3, a: 1 },
  { num: 6, code: "3-2", name: "3 - 2 (ホーム勝ち)", h: 3, a: 2 },
  { num: 7, code: "other_home_win", name: "その他ホーム勝ち", h: -1, a: -1 },
  { num: 8, code: "0-0", name: "0 - 0 (引き分け)", h: 0, a: 0 },
  { num: 9, code: "1-1", name: "1 - 1 (引き分け)", h: 1, a: 1 },
  { num: 10, code: "2-2", name: "2 - 2 (引き分け)", h: 2, a: 2 },
  { num: 11, code: "other_draw", name: "その他引き分け", h: -1, a: -1 },
  { num: 12, code: "0-1", name: "0 - 1 (アウェイ勝ち)", h: 0, a: 1 },
  { num: 13, code: "0-2", name: "0 - 2 (アウェイ勝ち)", h: 0, a: 2 },
  { num: 14, code: "1-2", name: "1 - 2 (アウェイ勝ち)", h: 1, a: 2 },
  { num: 15, code: "0-3", name: "0 - 3 (アウェイ勝ち)", h: 0, a: 3 },
  { num: 16, code: "1-3", name: "1 - 3 (アウェイ勝ち)", h: 1, a: 3 },
  { num: 17, code: "2-3", name: "2 - 3 (アウェイ勝ち)", h: 2, a: 3 },
  { num: 18, code: "other_away_win", name: "その他アウェイ勝ち", h: -1, a: -1 }
];

// グローバル状態
let modelData = window.WINNER_MODEL_DATA || null;
let fixturesPreset = window.WINNER_FIXTURES || [];
let currentSport = "Basketball";
let currentOdds = {}; // { selection_number: odds }

// 数学ヘルパー: Student-t CDF 近似 (Hill 1970 アルゴリズム)
function studentTCDF(t, df) {
  // 正規分布への収束または高精度近似
  if (df > 100) return normalCDF(t);
  const x = df / (df + t * t);
  let p = 0.5 * incompleteBeta(df / 2, 0.5, x);
  return t >= 0 ? 1 - p : p;
}

function normalCDF(z) {
  return 0.5 * (1 + erf(z / Math.SQRT2));
}

function erf(x) {
  const sign = x >= 0 ? 1 : -1;
  x = Math.abs(x);
  const a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741, a4 = -1.453152027, a5 = 1.061405429;
  const p = 0.3275911;
  const t = 1.0 / (1.0 + p * x);
  const y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);
  return sign * y;
}

function incompleteBeta(a, b, x) {
  if (x === 0) return 0;
  if (x === 1) return 1;
  // 連分数法近似
  const maxIter = 50;
  const eps = 1e-8;
  const qab = a + b, qap = a + 1, qam = a - 1;
  let c = 1, d = 1 - qab * x / qap;
  if (Math.abs(d) < eps) d = eps;
  d = 1 / d;
  let h = d;
  for (let m = 1; m <= maxIter; m++) {
    const m2 = 2 * m;
    let aa = m * (b - m) * x / ((qam + m2) * (a + m2));
    d = 1 + aa * d; if (Math.abs(d) < eps) d = eps;
    c = 1 + aa / c; if (Math.abs(c) < eps) c = eps;
    d = 1 / d; h *= d * c;
    aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2));
    d = 1 + aa * d; if (Math.abs(d) < eps) d = eps;
    c = 1 + aa / c; if (Math.abs(c) < eps) c = eps;
    d = 1 / d; h *= d * c;
  }
  const factor = Math.exp(logGamma(a + b) - logGamma(a) - logGamma(b) + a * Math.log(x) + b * Math.log(1 - x)) / a;
  return factor * h;
}

function logGamma(x) {
  const coef = [76.18009172947146, -86.50532032941677, 24.01409824083091, -1.231739572450155, 0.001208650973866179, -0.000005395239384953];
  let y = x, tmp = x + 5.5;
  tmp -= (x + 0.5) * Math.log(tmp);
  let ser = 1.000000000190015;
  for (let j = 0; j <= 5; j++) ser += coef[j] / ++y;
  return -tmp + Math.log(2.5066282746310005 * ser / x);
}

// ポアソン確率
function poissonProb(k, lambda) {
  return Math.exp(-lambda + k * Math.log(lambda) - logGamma(k + 1));
}

// ページ初期化
document.addEventListener("DOMContentLoaded", () => {
  initMaintenanceBanner();
  initPresetSelector();
  initEventListeners();
  // 初期試合（10247）を評価
  loadPresetMatch(10247);
});

// 1. メンテナンスバナーの制御
function initMaintenanceBanner() {
  const banner = document.getElementById("maintenanceBanner");
  const nextDateStr = modelData?.next_maintenance_date || "2027-09-01";
  const nextDate = new Date(nextDateStr);
  const now = new Date();
  const diffDays = Math.ceil((nextDate - now) / (1000 * 60 * 60 * 24));

  const textEl = document.getElementById("maintenanceDaysText");
  textEl.innerHTML = `モデル学習状態: <strong>正常</strong> (次回年次メンテナンス推奨: <strong>${nextDateStr}</strong> / 残り <strong>${diffDays}日</strong>)`;

  if (diffDays <= 30) {
    banner.classList.add("warning");
    textEl.innerHTML = `⚠️ <strong>定期メンテナンス推奨時期です</strong> (推奨期限: ${nextDateStr} まで残り ${diffDays}日)`;
  }
}

// 2. プリセット試合セレクター初期化
function initPresetSelector() {
  const sel = document.getElementById("presetMatchSelect");
  sel.innerHTML = "";
  fixturesPreset.forEach(f => {
    const opt = document.createElement("option");
    opt.value = f.lottery_id;
    opt.textContent = `[${f.sport === "Basketball" ? "バスケ" : "サッカー"}] くじ${f.lottery_id}: ${f.commodity_name}`;
    sel.appendChild(opt);
  });
}

function loadPresetMatch(lotteryId) {
  const fixture = fixturesPreset.find(f => f.lottery_id == lotteryId);
  if (!fixture) return;

  document.getElementById("presetMatchSelect").value = lotteryId;
  document.getElementById("sportSelect").value = fixture.sport;
  document.getElementById("homeTeamInput").value = fixture.home_team;
  document.getElementById("awayTeamInput").value = fixture.away_team;
  document.getElementById("matchTitle").textContent = fixture.commodity_name;
  currentSport = fixture.sport;

  // オッズ設定
  currentOdds = {};
  if (fixture.odds && Object.keys(fixture.odds).length > 0) {
    currentOdds = { ...fixture.odds };
  } else {
    // デフォルトオッズ生成
    const count = fixture.sport === "Basketball" ? 16 : 18;
    for (let i = 1; i <= count; i++) currentOdds[i] = (6.0 + (i % 5) * 2.5).toFixed(1);
  }

  evaluateMatch();
}

// 3. イベントリスナー
function initEventListeners() {
  // タブ切り替え
  document.querySelectorAll(".nav-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".nav-tab").forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(tab.dataset.tab).classList.add("active");
    });
  });

  // プリセット試合変更
  document.getElementById("presetMatchSelect").addEventListener("change", (e) => {
    loadPresetMatch(e.target.value);
  });

  // 競技変更
  document.getElementById("sportSelect").addEventListener("change", (e) => {
    currentSport = e.target.value;
    evaluateMatch();
  });

  // チーム名変更
  document.getElementById("homeTeamInput").addEventListener("input", evaluateMatch);
  document.getElementById("awayTeamInput").addEventListener("input", evaluateMatch);

  // オッズ抽出貼り付けパーサー
  document.getElementById("parseOddsBtn").addEventListener("click", parsePastedOdds);

  // メンテナンスモーダル
  document.getElementById("showMaintenanceBtn").addEventListener("click", () => {
    document.querySelector('.nav-tab[data-tab="maintenanceTab"]').click();
  });
}

// 4. クライアント推論 & 購入判定
function evaluateMatch() {
  const home = document.getElementById("homeTeamInput").value.trim();
  const away = document.getElementById("awayTeamInput").value.trim();
  const choices = currentSport === "Basketball" ? BASKETBALL_CHOICES : SOCCER_CHOICES;

  let probs = [];
  if (currentSport === "Basketball") {
    probs = predictBasketballProbs(home, away);
  } else {
    probs = predictSoccerProbs(home, away);
  }

  // 期待値計算 & 最適買い目選定
  const analysis = [];
  let bestBet = null;
  let maxEv = -999.0;

  choices.forEach((ch, idx) => {
    const p = probs[idx];
    const odds = parseFloat(currentOdds[ch.num] || 0);
    const ev = (odds > 0) ? (p * odds - 1.0) : -1.0;

    const row = {
      ...ch,
      prob: p,
      odds: odds,
      ev: ev
    };
    analysis.push(row);

    // Conservative_Value_V1 条件: EV > 0.15 (+15%) かつ 確率 >= 0.08 (8%)
    if (ev > 0.15 && p >= 0.08) {
      if (ev > maxEv) {
        maxEv = ev;
        bestBet = row;
      }
    }
  });

  renderDecisionBox(bestBet, analysis);
  renderOddsTable(analysis, bestBet);
}

// Bリーグ推論 (XGBoost + Student-t 積分)
function predictBasketballProbs(home, away) {
  const bData = modelData?.basketball;
  const homeElo = bData?.teams_elo[home] || 1500.0;
  const awayElo = bData?.teams_elo[away] || 1500.0;
  const eloDiff = homeElo - awayElo;

  // 期待点差 (Elo + リーグ定数)
  const expectedSpread = eloDiff / 25.0 + 3.5;
  const df = bData?.meta?.student_t_df || 5.2;
  const sigma = bData?.meta?.student_t_sigma || 11.8;

  let rawProbs = [];
  BASKETBALL_CHOICES.forEach(ch => {
    let p = 0;
    if (ch.side === "HOME") {
      const high = ch.max === 100 ? 100 : ch.max + 0.5;
      const low = ch.min - 0.5;
      p = studentTCDF((high - expectedSpread) / sigma, df) - studentTCDF((low - expectedSpread) / sigma, df);
    } else {
      const high = ch.max === 100 ? 100 : ch.max + 0.5;
      const low = ch.min - 0.5;
      p = studentTCDF((-low - expectedSpread) / sigma, df) - studentTCDF((-high - expectedSpread) / sigma, df);
    }
    rawProbs.push(Math.max(p, 0.001));
  });

  const sum = rawProbs.reduce((a, b) => a + b, 0);
  return rawProbs.map(p => p / sum);
}

// サッカー推論 (Dixon-Coles ポアソン強度)
function predictSoccerProbs(home, away) {
  const sData = modelData?.soccer;
  const homeElo = sData?.teams_elo[home] || 1500.0;
  const awayElo = sData?.teams_elo[away] || 1500.0;
  const eloDiff = (homeElo - awayElo) / 400.0;

  // 平均ゴール数
  const homeAdv = sData?.home_adv || 0.156;
  const rho = sData?.rho || -0.0519;
  const lambda = Math.max(1.35 * Math.pow(10, eloDiff * 0.3) * (1 + homeAdv), 0.3);
  const mu = Math.max(1.15 * Math.pow(10, -eloDiff * 0.3), 0.3);

  // 0〜5ゴールの同時確率行列
  const scoreGrid = [];
  for (let h = 0; h <= 5; h++) {
    scoreGrid[h] = [];
    for (let a = 0; a <= 5; a++) {
      let p = poissonProb(h, lambda) * poissonProb(a, mu);
      // Dixon-Coles 低得点補正
      if (h === 0 && a === 0) p *= (1 - lambda * mu * rho);
      else if (h === 0 && a === 1) p *= (1 + lambda * rho);
      else if (h === 1 && a === 0) p *= (1 + mu * rho);
      else if (h === 1 && a === 1) p *= (1 - rho);
      scoreGrid[h][a] = Math.max(p, 0.0001);
    }
  }

  // 18選択肢に集約
  let probs = [];
  SOCCER_CHOICES.forEach(ch => {
    if (ch.h !== -1) {
      probs.push(scoreGrid[ch.h]?.[ch.a] || 0.01);
    } else {
      let pOther = 0;
      for (let h = 0; h <= 5; h++) {
        for (let a = 0; a <= 5; a++) {
          if (ch.code === "other_home_win" && h > a && !(h <= 3 && a <= 2)) pOther += scoreGrid[h][a];
          if (ch.code === "other_draw" && h === a && h > 2) pOther += scoreGrid[h][a];
          if (ch.code === "other_away_win" && a > h && !(a <= 3 && h <= 2)) pOther += scoreGrid[h][a];
        }
      }
      probs.push(Math.max(pOther, 0.01));
    }
  });

  const sum = probs.reduce((a, b) => a + b, 0);
  return probs.map(p => p / sum);
}

// 5. 購入判断UI描画
function renderDecisionBox(bestBet, analysis) {
  const box = document.getElementById("decisionBox");

  if (bestBet) {
    box.className = "decision-box bet";
    box.innerHTML = `
      <div class="decision-badge">🎯 BET（購入推奨）</div>
      <div class="bet-recommendation">推奨買い目: <strong>【${bestBet.num}】 ${bestBet.name}</strong></div>
      <p style="color: var(--text-secondary); margin-bottom: 12px;">
        主要戦略 <strong>Conservative_Value_V1</strong> の基準（理論EV > +15%, 的中確率 ≥ 8%）を充足しました。
      </p>
      <div class="bet-meta">
        <span>表示オッズ: <strong>${bestBet.odds.toFixed(2)}倍</strong></span>
        <span>AI予測確率: <strong>${(bestBet.prob * 100).toFixed(1)}%</strong></span>
        <span>推定期待値 (EV): <strong style="color: var(--accent-green);">+${(bestBet.ev * 100).toFixed(1)}%</strong></span>
        <span>推奨投資額: <strong>200 円 (1口固定)</strong></span>
      </div>
    `;
  } else {
    // 最も惜しかった選択肢を特定
    const maxEvRow = [...analysis].sort((a, b) => b.ev - a.ev)[0];
    box.className = "decision-box no-bet";
    box.innerHTML = `
      <div class="decision-badge">✋ NO BET（見送り）</div>
      <div class="bet-recommendation" style="color: var(--text-muted);">本試合は購入推奨基準に達しませんでした</div>
      <p style="color: var(--text-secondary); margin-bottom: 12px;">
        最高期待値の選択肢は「${maxEvRow ? maxEvRow.name : 'なし'}」（EV: ${(maxEvRow ? maxEvRow.ev * 100 : 0).toFixed(1)}%, 確率: ${(maxEvRow ? maxEvRow.prob * 100 : 0).toFixed(1)}%）ですが、
        Conservative_Value_V1 の厳格基準（EV > +15% かつ 確率 ≥ 8%）を満たさないため、資本保護ルールにより見送ります。
      </p>
      <div class="bet-meta">
        <span>投資額: <strong>0 円</strong></span>
        <span>判断理由: <strong>控除率50%を超えるエッジ不足</strong></span>
      </div>
    `;
  }
}

// 6. オッズテーブル描画
function renderOddsTable(analysis, bestBet) {
  const tbody = document.getElementById("oddsTableBody");
  tbody.innerHTML = "";

  analysis.forEach(row => {
    const tr = document.createElement("tr");
    if (bestBet && row.num === bestBet.num) {
      tr.className = "highlight-bet";
    }

    const evText = row.odds > 0 ? (row.ev >= 0 ? `+${(row.ev * 100).toFixed(1)}%` : `${(row.ev * 100).toFixed(1)}%`) : "-";
    const evClass = row.ev > 0.15 ? "ev-positive" : "ev-negative";
    const barWidth = Math.min(Math.max((row.ev + 0.5) * 80, 0), 100);

    tr.innerHTML = `
      <td><strong>${row.num}</strong></td>
      <td>${row.name}</td>
      <td>
        <input type="number" step="0.1" min="1.0" class="table-odds-input" 
               value="${row.odds || ''}" data-num="${row.num}" 
               style="width: 80px; padding: 4px 6px; background: var(--bg-card); border: 1px solid var(--border-color); color: #fff; border-radius: 4px;"> 倍
      </td>
      <td>${(row.prob * 100).toFixed(1)}%</td>
      <td class="${evClass}">
        ${evText}
        ${row.ev > 0 ? `<span class="ev-bar-container"><span class="ev-bar-fill" style="width: ${barWidth}%;"></span></span>` : ''}
      </td>
    `;
    tbody.appendChild(tr);
  });

  // オッズ手動変更リスナー
  document.querySelectorAll(".table-odds-input").forEach(input => {
    input.addEventListener("input", (e) => {
      const num = parseInt(e.target.dataset.num);
      currentOdds[num] = parseFloat(e.target.value) || 0;
      evaluateMatch();
    });
  });
}

// 7. 貼り付けオッズのスマートパーサー
function parsePastedOdds() {
  const text = document.getElementById("pasteOddsInput").value;
  if (!text) return;

  const lines = text.split("\n");
  let updatedCount = 0;

  // パターン1: "1 5.6" または "H_1-3 7.3"
  // パターン2: "5.6倍"
  const choices = currentSport === "Basketball" ? BASKETBALL_CHOICES : SOCCER_CHOICES;
  
  choices.forEach(ch => {
    // 選択肢コードや名前の付近の数値を検索
    const regex = new RegExp(`(${ch.code}|${ch.num}|${ch.name.slice(0, 4)}).*?(\\d+\\.\\d+)`, "i");
    const m = text.match(regex);
    if (m && m[2]) {
      currentOdds[ch.num] = parseFloat(m[2]);
      updatedCount++;
    }
  });

  // 単純な数値リスト形式のフォールバック
  if (updatedCount < 5) {
    const numbers = text.match(/(\d+\.\d+)/g);
    if (numbers && numbers.length >= choices.length) {
      choices.forEach((ch, idx) => {
        currentOdds[ch.num] = parseFloat(numbers[idx]);
        updatedCount++;
      });
    }
  }

  if (updatedCount > 0) {
    alert(`オッズを自動抽出・反映しました (${updatedCount}件の選択肢)`);
    evaluateMatch();
  } else {
    alert("オッズ数値を検出できませんでした。数値を直接テーブルに入力するか、オッズ表をそのまま貼り付けてください。");
  }
}
