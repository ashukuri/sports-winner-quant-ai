#!/usr/bin/env python3
"""
src/strategy/toto_simulator.py
toto (13試合) および mini toto (5試合) のシミュレーションモジュール
- 各開催回におけるモデル推定確率に基づくシングル買い目およびマルチ買い目生成
- mini toto (A組・B組) の1等的中判定
- toto の1等 (13全的中)、2等 (12的中)、3等 (11的中) 判定
- 実際の公式当せん金に基づく回収率(ROI)、総損益、的中率の計算
"""

import numpy as np
import pandas as pd

class TotoSimulator:
    def __init__(self, cost_per_bet=100):
        self.cost_per_bet = cost_per_bet

    def simulate_mini_toto(self, rounds_data, model_probs_dict):
        """
        mini toto (5試合) のバックテスト
        rounds_data: list of dict, 各回5試合の [match_results (H/D/A), payout_1st (円)]
        model_probs_dict: 各モデルごとの各試合予測確率 (5, 3) のリスト
        """
        results_summary = {}
        LABEL_MAP = {'H': 0, 'D': 1, 'A': 2}
        INV_MAP = {0: 'H', 1: 'D', 2: 'A'}

        for model_name, probs_list in model_probs_dict.items():
            total_cost = 0
            total_return = 0
            first_prize_hits = 0
            n_rounds = len(rounds_data)
            matches_correct_list = []

            for r_idx in range(n_rounds):
                r_info = rounds_data[r_idx]
                true_results = r_info['results'] # list of 5 chars ('H'/'D'/'A')
                payout = r_info.get('payout_1st', 15000.0) # デフォルト約1.5万円

                probs_5 = probs_list[r_idx] # shape (5, 3)
                # モデルのTop-1予測
                preds = [INV_MAP[int(np.argmax(probs_5[i]))] for i in range(5)]

                # 一致数
                matches = sum(1 for p, t in zip(preds, true_results) if p == t)
                matches_correct_list.append(matches)

                total_cost += self.cost_per_bet
                if matches == 5:
                    first_prize_hits += 1
                    total_return += payout

            roi = (total_return - total_cost) / total_cost if total_cost > 0 else 0.0
            avg_correct = float(np.mean(matches_correct_list))

            results_summary[model_name] = {
                "n_rounds": n_rounds,
                "total_cost": total_cost,
                "total_return": total_return,
                "net_profit": total_return - total_cost,
                "roi": roi,
                "first_prize_hits": first_prize_hits,
                "hit_rate": first_prize_hits / n_rounds if n_rounds > 0 else 0.0,
                "avg_correct_matches": avg_correct
            }

        return pd.DataFrame(results_summary).T

    def simulate_full_toto(self, rounds_data, model_probs_dict):
        """
        toto (13試合) のバックテスト
        rounds_data: 各回13試合の [results, payout_1st, payout_2nd, payout_3rd]
        """
        results_summary = {}
        INV_MAP = {0: 'H', 1: 'D', 2: 'A'}

        for model_name, probs_list in model_probs_dict.items():
            total_cost = 0
            total_return = 0
            hits_1st = 0
            hits_2nd = 0
            hits_3rd = 0
            n_rounds = len(rounds_data)
            correct_counts = []

            for r_idx in range(n_rounds):
                r_info = rounds_data[r_idx]
                true_results = r_info['results']
                p1 = r_info.get('payout_1st', 10000000.0)
                p2 = r_info.get('payout_2nd', 100000.0)
                p3 = r_info.get('payout_3rd', 10000.0)

                probs_13 = probs_list[r_idx]
                preds = [INV_MAP[int(np.argmax(probs_13[i]))] for i in range(len(true_results))]

                matches = sum(1 for p, t in zip(preds, true_results) if p == t)
                correct_counts.append(matches)

                total_cost += self.cost_per_bet
                if matches == 13:
                    hits_1st += 1
                    total_return += p1
                elif matches == 12:
                    hits_2nd += 1
                    total_return += p2
                elif matches == 11:
                    hits_3rd += 1
                    total_return += p3

            roi = (total_return - total_cost) / total_cost if total_cost > 0 else 0.0

            results_summary[model_name] = {
                "n_rounds": n_rounds,
                "total_cost": total_cost,
                "total_return": total_return,
                "net_profit": total_return - total_cost,
                "roi": roi,
                "hits_1st": hits_1st,
                "hits_2nd": hits_2nd,
                "hits_3rd": hits_3rd,
                "avg_correct_matches": float(np.mean(correct_counts))
            }

        return pd.DataFrame(results_summary).T
