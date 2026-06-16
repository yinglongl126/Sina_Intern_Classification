#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Prepare Stage 2 ML/LLM training data from the 500-row category pilot.

Outputs:
  stage2_training_data.jsonl
  stage2_training_data_summary.md
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SOURCE_PATH = ROOT / "stage1_pilot_category_results_500.csv"
RULE_RESULTS_PATH = ROOT / "stage2_rule_validation_results.csv"
OUTPUT_JSONL_PATH = ROOT / "stage2_training_data.jsonl"
OUTPUT_SUMMARY_PATH = ROOT / "stage2_training_data_summary.md"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def text_len_bucket(text: str) -> str:
    length = len(text)
    if length < 80:
        return "short"
    if length < 260:
        return "medium"
    return "long"


def label_quality(row: dict[str, str], rule_row: dict[str, str] | None) -> str:
    if row.get("taxonomy_gap_candidate") == "TRUE":
        return "exclude_taxonomy_gap"
    if row.get("need_human_review") == "TRUE":
        return "weak_review_needed"
    if rule_row and rule_row.get("rule_matched") == "True" and rule_row.get("l2_agree_with_stage1") == "True":
        return "weak_high_rule_agree"
    return "weak_auto_pass"


def build_record(row: dict[str, str], rule_row: dict[str, str] | None) -> dict[str, Any]:
    title = (row.get("title") or "").strip()
    content = (row.get("content_summary") or "").strip()
    merchant = (row.get("merchant") or "").strip()
    platform = (row.get("platform") or "").strip()
    combined_text = "\n".join(
        part
        for part in [
            f"平台：{platform}" if platform else "",
            f"商家：{merchant}" if merchant else "",
            f"标题：{title}" if title else "",
            f"内容：{content}" if content else "",
        ]
        if part
    )
    quality = label_quality(row, rule_row)
    use_for_weak_train = quality in {"weak_high_rule_agree", "weak_auto_pass"}
    return {
        "sample_id": row.get("sample_id", ""),
        "complaint_id": row.get("complaint_id", ""),
        "platform": platform,
        "merchant": merchant,
        "title": title,
        "content_summary": content,
        "text": combined_text,
        "text_length": len(combined_text),
        "text_len_bucket": text_len_bucket(combined_text),
        "main_entity": row.get("main_entity", ""),
        "main_entity_type": row.get("main_entity_type", ""),
        "detected_product_entities": row.get("detected_product_entities", ""),
        "detected_service_entities": row.get("detected_service_entities", ""),
        "brand_info_used": row.get("brand_info_used", ""),
        "label": {
            "l1_code": row.get("l1_code", ""),
            "l1_name": row.get("l1_name", ""),
            "l2_code": row.get("l2_code", ""),
            "l2_name": row.get("l2_name", ""),
            "product_service_type": row.get("product_service_type", ""),
        },
        "label_quality": quality,
        "use_for_weak_train": use_for_weak_train,
        "need_human_review": row.get("need_human_review") == "TRUE",
        "taxonomy_gap_candidate": row.get("taxonomy_gap_candidate") == "TRUE",
        "category_confidence": float(row.get("category_confidence") or 0),
        "rule": {
            "matched": bool(rule_row and rule_row.get("rule_matched") == "True"),
            "rule_id": rule_row.get("rule_id", "") if rule_row else "",
            "entity": rule_row.get("rule_entity", "") if rule_row else "",
            "l2_code": rule_row.get("rule_l2_code", "") if rule_row else "",
            "l2_agree_with_stage1": rule_row.get("l2_agree_with_stage1") == "True" if rule_row else False,
        },
    }


def pct(n: int, d: int) -> str:
    return f"{n / d:.1%}" if d else "0.0%"


def write_summary(records: list[dict[str, Any]]) -> None:
    total = len(records)
    quality_counts = Counter(r["label_quality"] for r in records)
    train_records = [r for r in records if r["use_for_weak_train"]]
    l1_counts = Counter(r["label"]["l1_name"] for r in train_records)
    l2_counts = Counter(f'{r["label"]["l1_name"]} > {r["label"]["l2_name"]}' for r in train_records)
    bucket_counts = Counter(r["text_len_bucket"] for r in records)
    lines = [
        "# Stage 2 Training Data Summary",
        "",
        "## 1. 数据来源",
        "",
        "- 源文件：`stage1_pilot_category_results_500.csv`",
        "- 规则验证：`stage2_rule_validation_results.csv`",
        "- 输出数据：`stage2_training_data.jsonl`",
        "- 用途：供 LLM prompt、规则回归、传统 ML baseline、后续 MacBERT 微调共用。",
        "",
        "## 2. 总体统计",
        "",
        "| 指标 | 数量 | 比例 |",
        "|---|---:|---:|",
        f"| 总样本 | {total} | 100.0% |",
        f"| 可用于弱标签训练 | {len(train_records)} | {pct(len(train_records), total)} |",
        f"| 规则一致高信号样本 | {quality_counts.get('weak_high_rule_agree', 0)} | {pct(quality_counts.get('weak_high_rule_agree', 0), total)} |",
        f"| auto_pass 弱标签样本 | {quality_counts.get('weak_auto_pass', 0)} | {pct(quality_counts.get('weak_auto_pass', 0), total)} |",
        f"| 暂不用于训练：需复核 | {quality_counts.get('weak_review_needed', 0)} | {pct(quality_counts.get('weak_review_needed', 0), total)} |",
        f"| 暂不用于训练：taxonomy gap | {quality_counts.get('exclude_taxonomy_gap', 0)} | {pct(quality_counts.get('exclude_taxonomy_gap', 0), total)} |",
        "",
        "## 3. 文本长度分布",
        "",
        "| 长度桶 | 数量 |",
        "|---|---:|",
    ]
    for key in ["short", "medium", "long"]:
        lines.append(f"| {key} | {bucket_counts.get(key, 0)} |")
    lines.extend(
        [
            "",
            "## 4. 弱训练集 L1 分布",
            "",
            "| L1 | 数量 |",
            "|---|---:|",
        ]
    )
    for label, count in l1_counts.most_common():
        lines.append(f"| {label} | {count} |")
    lines.extend(
        [
            "",
            "## 5. 弱训练集 L2 TOP30",
            "",
            "| L2 | 数量 |",
            "|---|---:|",
        ]
    )
    for label, count in l2_counts.most_common(30):
        lines.append(f"| {label} | {count} |")
    lines.extend(
        [
            "",
            "## 6. 使用原则",
            "",
            "- 当前 JSONL 是弱标签训练数据，不是最终人工准确率评估集。",
            "- `use_for_weak_train=true` 的样本可用于第一版 ML baseline。",
            "- `weak_review_needed` 和 `exclude_taxonomy_gap` 暂不进入训练，可用于后续难例分析或 LLM 兜底测试。",
        ]
    )
    OUTPUT_SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    source_rows = read_csv(SOURCE_PATH)
    rule_rows = {r["sample_id"]: r for r in read_csv(RULE_RESULTS_PATH)}
    records = [build_record(row, rule_rows.get(row.get("sample_id", ""))) for row in source_rows]
    write_jsonl(OUTPUT_JSONL_PATH, records)
    write_summary(records)
    print(f"wrote {OUTPUT_JSONL_PATH.name}: {len(records)} records")
    print(f"wrote {OUTPUT_SUMMARY_PATH.name}")


if __name__ == "__main__":
    main()
