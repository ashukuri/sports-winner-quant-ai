#!/usr/bin/env python3
"""
src/backtest/evaluator.py
サッカー試合予測モデルの共通評価エンジン
- 1X2 Log Loss (主指標)
- Brier Score
- Accuracy (的中率)
- ECE (Expected Calibration Error)
- 市場予測 (Pinnacle/Market) との性能差および対応のあるt検定
- Bootstrap法による95%信頼区間算出
"""

import numpy as np
import pandas as pd
from scipy import stats

LABEL_MAP = {'H': 0, 'D': 1, 'A': 2}

def compute_log_loss_vector(y_true, prob_matrix):
    # y_true: array of 'H', 'D', 'A'
    # prob_matrix: (N, 3)
    losses = []
    for true_label, probs in zip(y_true, prob_matrix):
        c_idx = LABEL_MAP[true_label]
        p = max(probs[c_idx], 1e-12)
        losses.append(-np.log(p))
    return np.array(losses)

def compute_brier_score_vector(y_true, prob_matrix):
    # prob_matrix: (N, 3)
    briers = []
    for true_label, probs in zip(y_true, prob_matrix):
        target = np.zeros(3)
        target[LABEL_MAP[true_label]] = 1.0
        briers.append(np.sum((probs - target) ** 2))
    return np.array(briers)

def calculate_multiclass_ece(prob_matrix, y_true, n_bins=10):
    confidences = np.max(prob_matrix, axis=1)
    predictions = np.argmax(prob_matrix, axis=1)
    true_indices = np.array([LABEL_MAP[y] for y in y_true])
    accuracies = (predictions == true_indices).astype(float)

    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n_total = len(confidences)

    for i in range(n_bins):
        bin_lower, bin_upper = bin_boundaries[i], bin_boundaries[i + 1]
        mask = (confidences > bin_lower) & (confidences <= bin_upper)
        bin_count = np.sum(mask)
        if bin_count > 0:
            bin_acc = np.mean(accuracies[mask])
            bin_conf = np.mean(confidences[mask])
            ece += (bin_count / n_total) * np.abs(bin_acc - bin_conf)

    return float(ece)

def bootstrap_diff_ci(losses_model, losses_benchmark, n_boot=1000, alpha=0.05):
    diffs = np.array(losses_model) - np.array(losses_benchmark)
    n = len(diffs)
    boot_means = []
    np.random.seed(42)
    for _ in range(n_boot):
        sample = np.random.choice(diffs, size=n, replace=True)
        boot_means.append(np.mean(sample))
    
    ci_lower = float(np.percentile(boot_means, 100 * (alpha / 2)))
    ci_upper = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))
    mean_diff = float(np.mean(diffs))
    
    t_stat, p_val = stats.ttest_rel(losses_model, losses_benchmark)
    return {
        "mean_diff": mean_diff,
        "ci_lower_95": ci_lower,
        "ci_upper_95": ci_upper,
        "p_value": float(p_val)
    }

def evaluate_predictions(y_true, prob_matrix, model_name, market_prob_matrix=None):
    log_losses = compute_log_loss_vector(y_true, prob_matrix)
    brier_scores = compute_brier_score_vector(y_true, prob_matrix)
    preds = np.argmax(prob_matrix, axis=1)
    true_indices = np.array([LABEL_MAP[y] for y in y_true])
    acc = float(np.mean(preds == true_indices))
    ece = calculate_multiclass_ece(prob_matrix, y_true)

    # クラス別正解率
    acc_per_class = {}
    for label, c_idx in LABEL_MAP.items():
        mask = (true_indices == c_idx)
        if np.sum(mask) > 0:
            acc_per_class[f"acc_{label}"] = float(np.mean(preds[mask] == c_idx))
        else:
            acc_per_class[f"acc_{label}"] = 0.0

    res = {
        "model_name": model_name,
        "log_loss": float(np.mean(log_losses)),
        "brier_score": float(np.mean(brier_scores)),
        "accuracy": acc,
        "ece": ece,
        "acc_H": acc_per_class["acc_H"],
        "acc_D": acc_per_class["acc_D"],
        "acc_A": acc_per_class["acc_A"]
    }

    # 市場確率との直接比較 (オッズベンチマーク)
    if market_prob_matrix is not None:
        market_losses = compute_log_loss_vector(y_true, market_prob_matrix)
        boot_market = bootstrap_diff_ci(log_losses, market_losses)
        res["diff_vs_market"] = boot_market["mean_diff"]
        res["ci95_lower_vs_market"] = boot_market["ci_lower_95"]
        res["ci95_upper_vs_market"] = boot_market["ci_upper_95"]
        res["p_val_vs_market"] = boot_market["p_value"]

    return res, log_losses, brier_scores
