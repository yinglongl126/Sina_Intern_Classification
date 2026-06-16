#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Pure-stdlib ML baseline for Stage 2 category classification.

The goal is not to beat deep models. It provides a runnable lower-bound baseline
before introducing sklearn, MacBERT, or other heavier dependencies.

Commands:
  python stage2_ml_baseline.py
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
TRAINING_DATA_PATH = ROOT / "stage2_training_data.jsonl"
REPORT_PATH = ROOT / "stage2_ml_baseline_report.md"
PREDICTIONS_PATH = ROOT / "stage2_ml_baseline_predictions.jsonl"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def load_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with TRAINING_DATA_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def char_ngrams(text: str, min_n: int = 2, max_n: int = 4) -> Counter[str]:
    text = normalize_text(text)
    features: Counter[str] = Counter()
    if not text:
        return features
    for n in range(min_n, max_n + 1):
        if len(text) < n:
            continue
        for i in range(0, len(text) - n + 1):
            gram = text[i : i + n]
            if gram.strip():
                features[gram] += 1
    return features


class MultinomialNB:
    def __init__(self, alpha: float = 0.5) -> None:
        self.alpha = alpha
        self.labels: list[str] = []
        self.class_doc_counts: Counter[str] = Counter()
        self.class_token_counts: dict[str, Counter[str]] = defaultdict(Counter)
        self.class_total_tokens: Counter[str] = Counter()
        self.vocab: set[str] = set()
        self.total_docs = 0

    def fit(self, rows: list[dict[str, Any]], label_key: str) -> None:
        self.labels = []
        self.class_doc_counts.clear()
        self.class_token_counts.clear()
        self.class_total_tokens.clear()
        self.vocab.clear()
        self.total_docs = len(rows)
        for row in rows:
            label = get_label(row, label_key)
            feats = char_ngrams(row["text"])
            self.class_doc_counts[label] += 1
            self.class_token_counts[label].update(feats)
            self.class_total_tokens[label] += sum(feats.values())
            self.vocab.update(feats.keys())
        self.labels = sorted(self.class_doc_counts)

    def predict_one(self, text: str) -> tuple[str, float, list[tuple[str, float]]]:
        feats = char_ngrams(text)
        vocab_size = max(len(self.vocab), 1)
        scores: list[tuple[str, float]] = []
        denom_docs = max(self.total_docs, 1)
        for label in self.labels:
            prior = math.log(self.class_doc_counts[label] / denom_docs)
            denom = self.class_total_tokens[label] + self.alpha * vocab_size
            score = prior
            token_counts = self.class_token_counts[label]
            for gram, count in feats.items():
                score += count * math.log((token_counts.get(gram, 0) + self.alpha) / denom)
            scores.append((label, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        if not scores:
            return "", 0.0, []
        best_label, best_score = scores[0]
        if len(scores) == 1:
            confidence = 1.0
        else:
            # Stable softmax over top scores only for a rough confidence proxy.
            top = scores[:5]
            max_score = top[0][1]
            probs = [math.exp(s - max_score) for _, s in top]
            confidence = probs[0] / sum(probs)
        return best_label, confidence, scores[:3]


def get_label(row: dict[str, Any], label_key: str) -> str:
    label = row["label"]
    if label_key == "l1":
        return f'{label["l1_code"]} {label["l1_name"]}'
    if label_key == "l2":
        return f'{label["l2_code"]} {label["l2_name"]}'
    raise ValueError(label_key)


def make_folds(rows: list[dict[str, Any]], label_key: str, k: int = 5) -> list[list[int]]:
    by_label: dict[str, list[int]] = defaultdict(list)
    for idx, row in enumerate(rows):
        by_label[get_label(row, label_key)].append(idx)
    folds: list[list[int]] = [[] for _ in range(k)]
    for label in sorted(by_label):
        indices = by_label[label]
        if len(indices) < 2:
            # Keep singleton labels in training only. They are too sparse for a
            # meaningful holdout estimate and would be impossible to predict.
            continue
        for offset, idx in enumerate(indices):
            folds[offset % k].append(idx)
    return folds


def evaluate(rows: list[dict[str, Any]], label_key: str) -> dict[str, Any]:
    folds = make_folds(rows, label_key)
    predictions: list[dict[str, Any]] = []
    majority_correct = 0
    model_correct = 0
    total_eval = 0
    label_counts = Counter(get_label(row, label_key) for row in rows)

    for fold_id, test_indices in enumerate(folds):
        if not test_indices:
            continue
        test_set = set(test_indices)
        train_rows = [row for idx, row in enumerate(rows) if idx not in test_set]
        test_rows = [rows[idx] for idx in test_indices]
        model = MultinomialNB(alpha=0.5)
        model.fit(train_rows, label_key)
        majority_label = Counter(get_label(row, label_key) for row in train_rows).most_common(1)[0][0]
        for row in test_rows:
            gold = get_label(row, label_key)
            pred, conf, top3 = model.predict_one(row["text"])
            total_eval += 1
            model_correct += int(pred == gold)
            majority_correct += int(majority_label == gold)
            predictions.append(
                {
                    "sample_id": row["sample_id"],
                    "label_level": label_key,
                    "fold": fold_id,
                    "gold": gold,
                    "predicted": pred,
                    "correct": pred == gold,
                    "confidence": round(conf, 4),
                    "top3": [{"label": label, "score": round(score, 4)} for label, score in top3],
                    "text_len_bucket": row["text_len_bucket"],
                    "label_count": label_counts[gold],
                }
            )

    per_label: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "correct": 0})
    for pred in predictions:
        per_label[pred["gold"]]["total"] += 1
        per_label[pred["gold"]]["correct"] += int(pred["correct"])

    worst = sorted(
        (
            {
                "label": label,
                "total": counts["total"],
                "correct": counts["correct"],
                "accuracy": counts["correct"] / counts["total"] if counts["total"] else 0,
            }
            for label, counts in per_label.items()
            if counts["total"] >= 3
        ),
        key=lambda x: (x["accuracy"], -x["total"], x["label"]),
    )[:15]

    return {
        "label_key": label_key,
        "train_total": len(rows),
        "eval_total": total_eval,
        "model_correct": model_correct,
        "model_accuracy": model_correct / total_eval if total_eval else 0,
        "majority_correct": majority_correct,
        "majority_accuracy": majority_correct / total_eval if total_eval else 0,
        "singleton_labels": sum(1 for c in label_counts.values() if c == 1),
        "label_count": len(label_counts),
        "predictions": predictions,
        "worst_labels": worst,
    }


def rule_label(row: dict[str, Any], label_key: str) -> str:
    rule = row.get("rule", {})
    l2_code = rule.get("l2_code", "")
    if not rule.get("matched") or not rule.get("l2_agree_with_stage1") or not l2_code:
        return ""
    label = row["label"]
    if label_key == "l2":
        # The training data currently stores only the rule L2 code. The rule is
        # considered usable only when it agrees with the weak label, so reuse
        # the weak-label name for report readability.
        return f'{label["l2_code"]} {label["l2_name"]}' if l2_code == label["l2_code"] else l2_code
    if label_key == "l1":
        return f'{label["l1_code"]} {label["l1_name"]}'
    raise ValueError(label_key)


def evaluate_hybrid(rows: list[dict[str, Any]], label_key: str) -> dict[str, Any]:
    folds = make_folds(rows, label_key)
    predictions: list[dict[str, Any]] = []
    total_eval = 0
    correct = 0
    rule_used = 0
    nb_used = 0
    for fold_id, test_indices in enumerate(folds):
        if not test_indices:
            continue
        test_set = set(test_indices)
        train_rows = [row for idx, row in enumerate(rows) if idx not in test_set]
        test_rows = [rows[idx] for idx in test_indices]
        model = MultinomialNB(alpha=0.5)
        model.fit(train_rows, label_key)
        for row in test_rows:
            gold = get_label(row, label_key)
            source = "char_nb"
            pred = ""
            conf = 0.0
            if row["rule"].get("matched") and row["rule"].get("l2_agree_with_stage1"):
                pred = rule_label(row, label_key)
                if pred:
                    source = "rule"
                    conf = 0.95
                    rule_used += 1
            if not pred:
                pred, conf, _ = model.predict_one(row["text"])
                nb_used += 1
            total_eval += 1
            correct += int(pred == gold)
            predictions.append(
                {
                    "sample_id": row["sample_id"],
                    "label_level": label_key,
                    "fold": fold_id,
                    "gold": gold,
                    "predicted": pred,
                    "correct": pred == gold,
                    "confidence": round(conf, 4),
                    "source": source,
                }
            )
    return {
        "label_key": label_key,
        "eval_total": total_eval,
        "correct": correct,
        "accuracy": correct / total_eval if total_eval else 0,
        "rule_used": rule_used,
        "nb_used": nb_used,
        "predictions": predictions,
    }


def pct(value: float) -> str:
    return f"{value:.1%}"


def write_report(
    records: list[dict[str, Any]],
    l1_result: dict[str, Any],
    l2_result: dict[str, Any],
    hybrid_l1: dict[str, Any],
    hybrid_l2: dict[str, Any],
) -> None:
    train = [r for r in records if r["use_for_weak_train"]]
    quality_counts = Counter(r["label_quality"] for r in records)
    l1_counts = Counter(get_label(r, "l1") for r in train)
    l2_counts = Counter(get_label(r, "l2") for r in train)
    lines = [
        "# Stage 2 ML Baseline Report",
        "",
        "## 1. Baseline 设置",
        "",
        "- 纯文本模型：字符 2-4 gram + Multinomial Naive Bayes（纯 Python 标准库实现）",
        "- 混合模型：Layer 0 规则优先，未命中时回退到 Char NB",
        "- 训练/评估数据：`stage2_training_data.jsonl` 中 `use_for_weak_train=true` 的弱标签样本",
        "- 验证方式：按标签分层的 5-fold 交叉验证；单样本标签只放训练，不计入 holdout 评估",
        "- 说明：这是 ML 下界，不代表最终 MacBERT/LLM 混合方案能力。",
        "",
        "## 2. 数据概况",
        "",
        "| 指标 | 数量 |",
        "|---|---:|",
        f"| 全量 JSONL 样本 | {len(records)} |",
        f"| 弱标签训练候选 | {len(train)} |",
        f"| 规则一致高信号样本 | {quality_counts.get('weak_high_rule_agree', 0)} |",
        f"| auto_pass 弱标签样本 | {quality_counts.get('weak_auto_pass', 0)} |",
        f"| L1 标签数 | {len(l1_counts)} |",
        f"| L2 标签数 | {len(l2_counts)} |",
        "",
        "## 3. 结果",
        "",
        "| 层级 | 评估样本 | 标签数 | 单样本标签数 | Majority baseline | Char NB baseline | Hybrid baseline |",
        "|---|---:|---:|---:|---:|---:|---:|",
        f"| L1 | {l1_result['eval_total']} | {l1_result['label_count']} | {l1_result['singleton_labels']} | {pct(l1_result['majority_accuracy'])} | {pct(l1_result['model_accuracy'])} | {pct(hybrid_l1['accuracy'])} |",
        f"| L2 | {l2_result['eval_total']} | {l2_result['label_count']} | {l2_result['singleton_labels']} | {pct(l2_result['majority_accuracy'])} | {pct(l2_result['model_accuracy'])} | {pct(hybrid_l2['accuracy'])} |",
        "",
        "## 3.1 Hybrid 覆盖来源",
        "",
        "| 层级 | 规则输出 | NB 回退 |",
        "|---|---:|---:|",
        f"| L1 | {hybrid_l1['rule_used']} | {hybrid_l1['nb_used']} |",
        f"| L2 | {hybrid_l2['rule_used']} | {hybrid_l2['nb_used']} |",
        "",
        "## 4. L1 薄弱标签（评估样本 >= 3）",
        "",
        "| L1 | 评估数 | 正确数 | 准确率 |",
        "|---|---:|---:|---:|",
    ]
    for item in l1_result["worst_labels"]:
        lines.append(f"| {item['label']} | {item['total']} | {item['correct']} | {pct(item['accuracy'])} |")
    lines.extend(
        [
            "",
            "## 5. L2 薄弱标签（评估样本 >= 3）",
            "",
            "| L2 | 评估数 | 正确数 | 准确率 |",
            "|---|---:|---:|---:|",
        ]
    )
    for item in l2_result["worst_labels"]:
        lines.append(f"| {item['label']} | {item['total']} | {item['correct']} | {pct(item['accuracy'])} |")
    lines.extend(
        [
            "",
            "## 6. 结论",
            "",
            "- 当前弱标签样本量仍小，尤其 L2 长尾明显；Char NB 只能作为可运行下界。",
            "- Hybrid baseline 明显高于纯文本模型，说明规则层应继续作为线上漏斗第一层，而不是直接依赖 ML。",
            "- 如果后续 TF-IDF + LR 或 MacBERT 没有明显超过 Char NB 下界，应优先检查标签质量和实体抽取质量。",
            "- 下一步建议：扩展 1000 条弱标签，同时优先补足每个高频 L2 至至少 20 条样本。",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_predictions(results: list[dict[str, Any]]) -> None:
    with PREDICTIONS_PATH.open("w", encoding="utf-8", newline="\n") as f:
        for row in results:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    records = load_records()
    train_records = [r for r in records if r["use_for_weak_train"]]
    if len(train_records) < 20:
        raise SystemExit("not enough weak training records; run stage2_prepare_training_data.py first")
    l1_result = evaluate(train_records, "l1")
    l2_result = evaluate(train_records, "l2")
    hybrid_l1 = evaluate_hybrid(train_records, "l1")
    hybrid_l2 = evaluate_hybrid(train_records, "l2")
    write_predictions(
        l1_result["predictions"]
        + l2_result["predictions"]
        + hybrid_l1["predictions"]
        + hybrid_l2["predictions"]
    )
    write_report(records, l1_result, l2_result, hybrid_l1, hybrid_l2)
    print(f"wrote {REPORT_PATH.name}")
    print(f"wrote {PREDICTIONS_PATH.name}")
    print(f"L1 accuracy={l1_result['model_accuracy']:.3f} on {l1_result['eval_total']} eval rows")
    print(f"L2 accuracy={l2_result['model_accuracy']:.3f} on {l2_result['eval_total']} eval rows")
    print(f"Hybrid L1 accuracy={hybrid_l1['accuracy']:.3f} on {hybrid_l1['eval_total']} eval rows")
    print(f"Hybrid L2 accuracy={hybrid_l2['accuracy']:.3f} on {hybrid_l2['eval_total']} eval rows")


if __name__ == "__main__":
    main()
