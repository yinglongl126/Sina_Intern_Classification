#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Validate Stage 2 LLM classification outputs.

Usage:
  python stage2_validate_llm_outputs.py path/to/llm_outputs.jsonl

The input file should contain one JSON object per line, matching
stage2_llm_output_schema.json at the field level. This validator uses only the
Python standard library, so it checks required fields, enums, evidence shape,
and L1/L2 taxonomy consistency without requiring jsonschema.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
TAXONOMY_PATH = ROOT / "stage1_taxonomy.json"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def load_taxonomy() -> tuple[dict[str, str], dict[str, tuple[str, str, str]]]:
    taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8-sig"))
    l1_names = {item["code"]: item["name"] for item in taxonomy}
    l2_map: dict[str, tuple[str, str, str]] = {}
    for item in taxonomy:
        for l2 in item.get("l2", []):
            l2_map[l2["code"]] = (l2["name"], item["code"], item["name"])
    return l1_names, l2_map


def validate_obj(obj: dict[str, Any], l1_names: dict[str, str], l2_map: dict[str, tuple[str, str, str]]) -> list[str]:
    errors: list[str] = []
    required = [
        "sample_id",
        "main_entity",
        "main_entity_type",
        "primary_category",
        "confidence",
        "needs_review",
        "review_flags",
        "evidence",
        "auxiliary",
        "notes",
    ]
    for key in required:
        if key not in obj:
            errors.append(f"missing field: {key}")
    if errors:
        return errors

    if obj["main_entity_type"] not in {"PRODUCT", "SERVICE", "PLATFORM_SERVICE", "UNKNOWN"}:
        errors.append("invalid main_entity_type")
    if not isinstance(obj["confidence"], (int, float)) or not (0 <= obj["confidence"] <= 1):
        errors.append("confidence must be number between 0 and 1")
    if not isinstance(obj["needs_review"], bool):
        errors.append("needs_review must be boolean")
    if not isinstance(obj["review_flags"], list):
        errors.append("review_flags must be list")

    cat = obj.get("primary_category") or {}
    for key in ["l1_code", "l1_name", "l2_code", "l2_name", "product_service_type"]:
        if key not in cat:
            errors.append(f"missing primary_category.{key}")
    l1_code = cat.get("l1_code")
    l2_code = cat.get("l2_code")
    if l1_code not in l1_names:
        errors.append(f"invalid l1_code: {l1_code}")
    elif cat.get("l1_name") != l1_names[l1_code]:
        errors.append(f"l1_name mismatch: {l1_code} should be {l1_names[l1_code]}")
    if l2_code not in l2_map:
        errors.append(f"invalid l2_code: {l2_code}")
    else:
        l2_name, parent_code, parent_name = l2_map[l2_code]
        if cat.get("l2_name") != l2_name:
            errors.append(f"l2_name mismatch: {l2_code} should be {l2_name}")
        if l1_code != parent_code or cat.get("l1_name") != parent_name:
            errors.append(f"l2 parent mismatch: {l2_code} belongs to {parent_code} {parent_name}")

    if not isinstance(obj["evidence"], list):
        errors.append("evidence must be list")
    else:
        for idx, ev in enumerate(obj["evidence"]):
            if not isinstance(ev, dict):
                errors.append(f"evidence[{idx}] must be object")
                continue
            if ev.get("source_field") not in {"title", "content_summary", "merchant", "platform", "none"}:
                errors.append(f"invalid evidence[{idx}].source_field")
            if ev.get("supports") not in {"main_entity", "category", "brand", "exclusion", "ambiguity"}:
                errors.append(f"invalid evidence[{idx}].supports")
            if "text" not in ev:
                errors.append(f"missing evidence[{idx}].text")

    aux = obj.get("auxiliary")
    if not isinstance(aux, dict):
        errors.append("auxiliary must be object")
    else:
        for key in ["brand", "complaint_issue", "service_context"]:
            if key not in aux:
                errors.append(f"missing auxiliary.{key}")
    return errors


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python stage2_validate_llm_outputs.py path/to/llm_outputs.jsonl")
    path = Path(sys.argv[1])
    l1_names, l2_map = load_taxonomy()
    total = 0
    invalid = 0
    error_counts: Counter[str] = Counter()
    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            total += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                invalid += 1
                msg = f"line {line_no}: invalid json: {exc.msg}"
                error_counts[msg] += 1
                continue
            errors = validate_obj(obj, l1_names, l2_map)
            if errors:
                invalid += 1
                for err in errors:
                    error_counts[err] += 1
    print(f"total={total}")
    print(f"valid={total - invalid}")
    print(f"invalid={invalid}")
    if error_counts:
        print("top_errors:")
        for err, count in error_counts.most_common(20):
            print(f"- {count}: {err}")
    if invalid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
