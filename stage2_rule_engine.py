#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Layer 0 rule engine for product/service category classification.

Commands:
  python stage2_rule_engine.py build-assets
  python stage2_rule_engine.py validate
  python stage2_rule_engine.py classify-text "投诉标题" "投诉正文"
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
TAXONOMY_PATH = ROOT / "stage1_taxonomy.json"
RESULTS_500_PATH = ROOT / "stage1_pilot_category_results_500.csv"
PRODUCT_DICT_PATH = ROOT / "stage2_product_dictionary.json"
EXCLUSION_DICT_PATH = ROOT / "stage2_exclusion_dictionary.json"
VALIDATION_REPORT_PATH = ROOT / "stage2_rule_validation_report.md"
VALIDATION_RESULTS_PATH = ROOT / "stage2_rule_validation_results.csv"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


NON_ENTITY_TERMS = {
    "",
    "N/A",
    "无",
    "未知",
    "商品",
    "产品",
    "衣服",
    "服装",
    "外套",
    "羽绒服",
    "裤子",
    "东西",
    "货",
    "店铺",
    "店铺服务",
    "商家",
    "客服",
    "平台",
    "app",
    "APP",
    "App",
    "投诉",
    "退款",
    "退货",
    "售后",
    "订单",
    "快递",
    "物流",
    "配送",
    "直播",
    "保证金",
}

AMBIGUOUS_SHORT_TERMS = {
    "包",
    "猫",
    "狗",
    "笔",
    "卡",
    "券",
    "鞋",
    "床",
    "药",
    "鱼",
    "酒",
}

AMBIGUOUS_ENTITY_TERMS = {
    "苹果",
    "屏幕",
    "衣服",
    "服装",
    "外套",
    "羽绒服",
    "裤子",
    "商品",
    "产品",
    "店铺服务",
    "物流配送",
    "直播",
    "App",
    "app",
    "快递",
    "物流",
    "运费险",
}

EXTRA_PRODUCT_TERMS = [
    ("杯子", ["星巴克杯子", "水杯", "保温杯", "马克杯"], "07", "家居家装", "07-04", "厨房卫浴用品", "PRODUCT"),
    ("半日达配送", ["半日达", "晚到必赔", "配送超时", "未按时送达"], "20", "平台服务与账号服务", "20-04", "物流配送服务", "PLATFORM_SERVICE"),
    ("钢琴", ["AI智慧钢琴", "智慧钢琴", "重锤88键"], "12", "图书文娱与文创", "12-02", "文具与乐器", "PRODUCT"),
]

NEGATIVE_PHRASES = [
    # 包 is not a bag in these phrases.
    "三包",
    "包修",
    "包换",
    "包退",
    "包邮",
    "不包邮",
    "不包邮件",
    "包庇",
    "包括",
    "红包",
    "表情包",
    "包装",
    "包裹",
    "包装盒",
    "包赔",
    "包容",
    "包月",
    "两包尿不湿",
    "一包尿不湿",
    "几包尿不湿",
    # Cat/dog idioms or proper names, not pets.
    "猫腻",
    "天猫",
    "天猫超市",
    "挂羊头卖狗肉",
    "狗肉",
    # Pen as measure word, not stationery.
    "单笔",
    "多笔",
    "这笔",
    "那笔",
    "每笔",
    "一笔订单",
    # Context where the mentioned object is not the complained-about product.
    "帽子处",
    "包裹内是耳环",
    "绑定的别人手机",
    "绑定别人手机",
    "绑定手机号",
    "换绑定手机号",
    "手机号的验证码",
    "手机号",
    "别人手机",
]

PHRASE_RULES = [
    {
        "rule_id": "pattern_apple_digital",
        "patterns": ["苹果手机", "苹果15", "苹果16", "苹果17", "iphone", "iPhone", "promax", "Pro Max"],
        "l1_code": "06",
        "l1_name": "数码电子",
        "l2_code": "06-01",
        "l2_name": "手机通讯",
        "entity": "手机",
        "entity_type": "PRODUCT",
        "confidence": 0.94,
    },
    {
        "rule_id": "pattern_apple_fruit",
        "patterns": ["昭通苹果", "烟台苹果", "十斤苹果", "苹果烂", "苹果尺寸", "生鲜苹果"],
        "l1_code": "01",
        "l1_name": "食品生鲜",
        "l2_code": "01-04",
        "l2_name": "生鲜水果",
        "entity": "苹果",
        "entity_type": "PRODUCT",
        "confidence": 0.93,
    },
    {
        "rule_id": "pattern_half_day_delivery",
        "patterns": ["半日达", "晚到必赔", "未按时送达"],
        "l1_code": "20",
        "l1_name": "平台服务与账号服务",
        "l2_code": "20-04",
        "l2_name": "物流配送服务",
        "entity": "半日达配送",
        "entity_type": "PLATFORM_SERVICE",
        "confidence": 0.93,
    },
    {
        "rule_id": "pattern_delivery",
        "patterns": ["快递丢失", "物流不更新", "物流延误", "派送超时", "配送超时"],
        "l1_code": "20",
        "l1_name": "平台服务与账号服务",
        "l2_code": "20-04",
        "l2_name": "物流配送服务",
        "entity": "物流配送",
        "entity_type": "PLATFORM_SERVICE",
        "confidence": 0.9,
    },
    {
        "rule_id": "pattern_food_delivery",
        "patterns": ["骑手送餐", "外卖送餐", "餐品洒漏", "淘宝闪购骑手"],
        "l1_code": "16",
        "l1_name": "本地生活服务",
        "l2_code": "16-01",
        "l2_name": "餐饮外卖",
        "entity": "外卖配送",
        "entity_type": "SERVICE",
        "confidence": 0.9,
    },
    {
        "rule_id": "pattern_store_purchase_product_cup",
        "patterns": ["店铺购买星巴克杯子", "购买星巴克杯子", "杯子漏水", "盖子太紧"],
        "l1_code": "07",
        "l1_name": "家居家装",
        "l2_code": "07-04",
        "l2_name": "厨房卫浴用品",
        "entity": "杯子",
        "entity_type": "PRODUCT",
        "confidence": 0.95,
    },
]


@dataclass
class Match:
    term: str
    matched_text: str
    l1_code: str
    l1_name: str
    l2_code: str
    l2_name: str
    entity_type: str
    confidence: float
    source: str
    rule_id: str
    start: int
    end: int


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_term(term: str) -> str:
    return re.sub(r"\s+", "", (term or "").strip())


def clean_text(*parts: str) -> str:
    text = " ".join(p for p in parts if p)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def taxonomy_lookup(taxonomy: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for l1 in taxonomy:
        for l2 in l1.get("l2", []):
            lookup[l2["code"]] = {
                "l1_code": l1["code"],
                "l1_name": l1["name"],
                "l2_code": l2["code"],
                "l2_name": l2["name"],
            }
    return lookup


def add_entry(
    entries: dict[tuple[str, str], dict[str, Any]],
    term: str,
    aliases: list[str],
    l1_code: str,
    l1_name: str,
    l2_code: str,
    l2_name: str,
    entity_type: str,
    source: str,
    priority: int = 50,
) -> None:
    term = normalize_term(term)
    if not term or term in NON_ENTITY_TERMS or term in AMBIGUOUS_ENTITY_TERMS:
        return
    if len(term) < 2 or term in AMBIGUOUS_SHORT_TERMS:
        return
    key = (term, l2_code)
    alias_set = {normalize_term(a) for a in aliases if normalize_term(a)}
    alias_set.discard(term)
    if key in entries:
        entries[key]["aliases"] = sorted(set(entries[key]["aliases"]) | alias_set)
        entries[key]["sources"] = sorted(set(entries[key]["sources"]) | {source})
        entries[key]["priority"] = min(entries[key]["priority"], priority)
        return
    entries[key] = {
        "term": term,
        "aliases": sorted(alias_set),
        "l1_code": l1_code,
        "l1_name": l1_name,
        "l2_code": l2_code,
        "l2_name": l2_name,
        "entity_type": entity_type,
        "priority": priority,
        "sources": [source],
        "negative_context_terms": [],
    }


def build_assets() -> None:
    taxonomy = read_json(TAXONOMY_PATH)
    rows = read_csv(RESULTS_500_PATH)
    entries: dict[tuple[str, str], dict[str, Any]] = {}

    for l1 in taxonomy:
        for l2 in l1.get("l2", []):
            examples = [normalize_term(x) for x in l2.get("examples", [])]
            for ex in examples:
                add_entry(
                    entries,
                    ex,
                    [],
                    l1["code"],
                    l1["name"],
                    l2["code"],
                    l2["name"],
                    l1.get("type", "PRODUCT"),
                    "taxonomy_example",
                    priority=40,
                )

    for row in rows:
        entity = normalize_term(row.get("main_entity", ""))
        if row.get("l1_code") == "98":
            continue
        if row.get("main_entity_type") in {"PLATFORM_SERVICE", "UNKNOWN"}:
            continue
        add_entry(
            entries,
            entity,
            [],
            row["l1_code"],
            row["l1_name"],
            row["l2_code"],
            row["l2_name"],
            row.get("main_entity_type", "PRODUCT"),
            "stage1_500_main_entity",
            priority=30 if row.get("need_human_review") == "FALSE" else 45,
        )

    for term, aliases, l1_code, l1_name, l2_code, l2_name, entity_type in EXTRA_PRODUCT_TERMS:
        add_entry(
            entries,
            term,
            aliases,
            l1_code,
            l1_name,
            l2_code,
            l2_name,
            entity_type,
            "manual_high_precision_rule",
            priority=10,
        )

    product_dictionary = {
        "version": "stage2_rule_assets_v1",
        "description": "商品/服务实体到 L1/L2 的高精度规则词典。由 taxonomy 示例、500 条试标主实体和人工高精度规则合成。",
        "entry_count": len(entries),
        "entries": sorted(entries.values(), key=lambda x: (x["l1_code"], x["l2_code"], x["term"])),
    }
    exclusion_dictionary = {
        "version": "stage2_rule_assets_v1",
        "description": "用于阻止中文子串误匹配的排除词、量词、成语和上下文规则。",
        "negative_phrases": sorted(set(NEGATIVE_PHRASES), key=len, reverse=True),
        "blocked_single_char_terms": sorted(AMBIGUOUS_SHORT_TERMS),
        "phrase_rules": PHRASE_RULES,
        "notes": [
            "不要全局禁用真实商品词，例如 包包、书包、背包、购买一个包 仍可识别为箱包。",
            "排除词优先级高于商品词典命中。",
            "如果 evidence_text 中的实体不存在于原文，应视为无来源实体，不允许自动输出。",
        ],
    }

    write_json(PRODUCT_DICT_PATH, product_dictionary)
    write_json(EXCLUSION_DICT_PATH, exclusion_dictionary)
    print(f"wrote {PRODUCT_DICT_PATH.name}: {len(entries)} entries")
    print(f"wrote {EXCLUSION_DICT_PATH.name}: {len(exclusion_dictionary['negative_phrases'])} negative phrases")


def load_assets() -> tuple[dict[str, Any], dict[str, Any]]:
    if not PRODUCT_DICT_PATH.exists() or not EXCLUSION_DICT_PATH.exists():
        build_assets()
    return read_json(PRODUCT_DICT_PATH), read_json(EXCLUSION_DICT_PATH)


def excluded_spans(text: str, exclusion: dict[str, Any]) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    for phrase in exclusion.get("negative_phrases", []):
        start = text.find(phrase)
        while start >= 0:
            spans.append((start, start + len(phrase), phrase))
            start = text.find(phrase, start + 1)
    return spans


def overlaps_exclusion(start: int, end: int, spans: list[tuple[int, int, str]]) -> bool:
    return any(start < span_end and end > span_start for span_start, span_end, _ in spans)


def classify_text(title: str, content: str = "", merchant: str = "") -> dict[str, Any]:
    product_dict, exclusion = load_assets()
    text = clean_text(title, content, merchant)
    if not text:
        return {"matched": False, "reason": "empty_text"}

    # Highest priority: phrase rules.
    for rule in exclusion.get("phrase_rules", []):
        hits = [p for p in rule["patterns"] if p and p in text]
        if hits:
            return {
                "matched": True,
                "rule_id": rule["rule_id"],
                "main_entity": rule["entity"],
                "main_entity_type": rule["entity_type"],
                "l1_code": rule["l1_code"],
                "l1_name": rule["l1_name"],
                "l2_code": rule["l2_code"],
                "l2_name": rule["l2_name"],
                "confidence": rule["confidence"],
                "evidence_text": "; ".join(f"{h}[pattern]" for h in hits),
                "source": "phrase_rule",
            }

    spans = excluded_spans(text, exclusion)
    matches: list[Match] = []

    for entry in product_dict["entries"]:
        terms = [entry["term"], *entry.get("aliases", [])]
        for term in terms:
            if not term or term in exclusion.get("blocked_single_char_terms", []):
                continue
            start = text.find(term)
            while start >= 0:
                end = start + len(term)
                if not overlaps_exclusion(start, end, spans):
                    confidence = 0.95 if entry["priority"] <= 10 else 0.9 if entry["priority"] <= 30 else 0.85
                    matches.append(
                        Match(
                            term=entry["term"],
                            matched_text=term,
                            l1_code=entry["l1_code"],
                            l1_name=entry["l1_name"],
                            l2_code=entry["l2_code"],
                            l2_name=entry["l2_name"],
                            entity_type=entry["entity_type"],
                            confidence=confidence,
                            source="+".join(entry.get("sources", [])),
                            rule_id="dictionary_exact_match",
                            start=start,
                            end=end,
                        )
                    )
                start = text.find(term, start + 1)

    if not matches:
        return {"matched": False, "reason": "no_rule_match"}

    # Prefer longer evidence, higher-confidence manual/entity sources, then earlier title hits.
    matches.sort(key=lambda m: (m.confidence, len(m.matched_text), -m.start), reverse=True)
    best = matches[0]
    return {
        "matched": True,
        "rule_id": best.rule_id,
        "main_entity": best.term,
        "main_entity_type": best.entity_type,
        "l1_code": best.l1_code,
        "l1_name": best.l1_name,
        "l2_code": best.l2_code,
        "l2_name": best.l2_name,
        "confidence": best.confidence,
        "evidence_text": f"{best.matched_text}[rule]",
        "source": best.source,
    }


def validate() -> None:
    load_assets()
    rows = read_csv(RESULTS_500_PATH)
    out_rows: list[dict[str, Any]] = []
    matched_rows = 0
    l1_agree = 0
    l2_agree = 0
    auto_pass_matches = 0
    auto_pass_l2_agree = 0
    by_l2 = Counter()
    error_examples: list[dict[str, Any]] = []

    for row in rows:
        result = classify_text(row.get("title", ""), row.get("content_summary", ""), row.get("merchant", ""))
        matched = bool(result.get("matched"))
        if matched:
            matched_rows += 1
            by_l2[f"{result['l2_code']} {result['l2_name']}"] += 1
            if result["l1_code"] == row.get("l1_code"):
                l1_agree += 1
            if result["l2_code"] == row.get("l2_code"):
                l2_agree += 1
            if row.get("need_human_review") == "FALSE":
                auto_pass_matches += 1
                if result["l2_code"] == row.get("l2_code"):
                    auto_pass_l2_agree += 1
            if result["l2_code"] != row.get("l2_code") and len(error_examples) < 20:
                error_examples.append(
                    {
                        "sample_id": row["sample_id"],
                        "title": row["title"],
                        "gold_l2": f"{row['l2_code']} {row['l2_name']}",
                        "rule_l2": f"{result['l2_code']} {result['l2_name']}",
                        "evidence": result["evidence_text"],
                    }
                )

        out_rows.append(
            {
                "sample_id": row.get("sample_id"),
                "title": row.get("title"),
                "gold_l1_code": row.get("l1_code"),
                "gold_l1_name": row.get("l1_name"),
                "gold_l2_code": row.get("l2_code"),
                "gold_l2_name": row.get("l2_name"),
                "need_human_review": row.get("need_human_review"),
                "rule_matched": matched,
                "rule_id": result.get("rule_id", ""),
                "rule_entity": result.get("main_entity", ""),
                "rule_l1_code": result.get("l1_code", ""),
                "rule_l1_name": result.get("l1_name", ""),
                "rule_l2_code": result.get("l2_code", ""),
                "rule_l2_name": result.get("l2_name", ""),
                "rule_confidence": result.get("confidence", ""),
                "rule_evidence": result.get("evidence_text", ""),
                "rule_source": result.get("source", ""),
                "l1_agree_with_stage1": matched and result.get("l1_code") == row.get("l1_code"),
                "l2_agree_with_stage1": matched and result.get("l2_code") == row.get("l2_code"),
            }
        )

    write_csv(
        VALIDATION_RESULTS_PATH,
        out_rows,
        [
            "sample_id",
            "title",
            "gold_l1_code",
            "gold_l1_name",
            "gold_l2_code",
            "gold_l2_name",
            "need_human_review",
            "rule_matched",
            "rule_id",
            "rule_entity",
            "rule_l1_code",
            "rule_l1_name",
            "rule_l2_code",
            "rule_l2_name",
            "rule_confidence",
            "rule_evidence",
            "rule_source",
            "l1_agree_with_stage1",
            "l2_agree_with_stage1",
        ],
    )

    product_dict = read_json(PRODUCT_DICT_PATH)
    exclusion = read_json(EXCLUSION_DICT_PATH)
    total = len(rows)
    report = []
    report.append("# Stage 2 Layer 0 规则引擎验证报告")
    report.append("")
    report.append("## 1. 资产概况")
    report.append("")
    report.append(f"- 商品/服务词典：`stage2_product_dictionary.json`，{product_dict['entry_count']} 条词条")
    report.append(f"- 排除词词典：`stage2_exclusion_dictionary.json`，{len(exclusion['negative_phrases'])} 条排除短语")
    report.append(f"- 验证样本：`stage1_pilot_category_results_500.csv`，{total} 条")
    report.append("")
    report.append("## 2. 验证结果")
    report.append("")
    report.append("| 指标 | 数值 | 说明 |")
    report.append("|---|---:|---|")
    report.append(f"| 规则命中样本 | {matched_rows}/{total} ({matched_rows / total:.1%}) | Layer 0 覆盖率 |")
    report.append(f"| L1 与现有试标一致 | {l1_agree}/{matched_rows} ({(l1_agree / matched_rows if matched_rows else 0):.1%}) | 弱标签一致性，不等于真实准确率 |")
    report.append(f"| L2 与现有试标一致 | {l2_agree}/{matched_rows} ({(l2_agree / matched_rows if matched_rows else 0):.1%}) | 弱标签一致性，不等于真实准确率 |")
    report.append(f"| auto_pass 命中样本 | {auto_pass_matches} | 当前可作为高信号规则覆盖候选 |")
    report.append(f"| auto_pass L2 一致 | {auto_pass_l2_agree}/{auto_pass_matches} ({(auto_pass_l2_agree / auto_pass_matches if auto_pass_matches else 0):.1%}) | 需要抽样人工确认 |")
    report.append("")
    report.append("## 3. 规则命中 L2 TOP20")
    report.append("")
    report.append("| L2 | 命中数 |")
    report.append("|---|---:|")
    for name, count in by_l2.most_common(20):
        report.append(f"| {name} | {count} |")
    report.append("")
    report.append("## 4. 不一致样本示例")
    report.append("")
    if not error_examples:
        report.append("未发现规则输出与现有试标不一致的样本。")
    else:
        report.append("| sample_id | 当前试标 L2 | 规则 L2 | evidence | title |")
        report.append("|---|---|---|---|---|")
        for item in error_examples:
            title = item["title"].replace("|", " ")
            report.append(f"| {item['sample_id']} | {item['gold_l2']} | {item['rule_l2']} | {item['evidence']} | {title} |")
    report.append("")
    report.append("## 5. 结论")
    report.append("")
    report.append("- 当前 Layer 0 是第一版高精度规则基线，覆盖率和一致性还需要继续调参。")
    report.append("- 报告中的一致性以现有 500 条试标为参照，不代表真实准确率。")
    report.append("- 下一步应人工抽查规则命中的不一致样本，决定是修词典、修排除词，还是修 500 条弱标签。")
    VALIDATION_REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"matched={matched_rows}/{total}")
    print(f"l1_agreement={l1_agree}/{matched_rows}")
    print(f"l2_agreement={l2_agree}/{matched_rows}")
    print(f"wrote {VALIDATION_RESULTS_PATH.name}")
    print(f"wrote {VALIDATION_REPORT_PATH.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 2 Layer 0 rule engine")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("build-assets")
    subparsers.add_parser("validate")
    classify_parser = subparsers.add_parser("classify-text")
    classify_parser.add_argument("title")
    classify_parser.add_argument("content", nargs="?", default="")
    classify_parser.add_argument("--merchant", default="")
    args = parser.parse_args()

    if args.command == "build-assets":
        build_assets()
    elif args.command == "validate":
        validate()
    elif args.command == "classify-text":
        print(json.dumps(classify_text(args.title, args.content, args.merchant), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
