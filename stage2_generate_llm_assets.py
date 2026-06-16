#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generate Stage 2 LLM prompt, output schema, and test cases.

Outputs:
  stage2_llm_output_schema.json
  stage2_llm_prompt_v2.md
  stage2_llm_test_cases.jsonl
  stage2_llm_test_cases_summary.md
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
TAXONOMY_PATH = ROOT / "stage1_taxonomy.json"
TRAINING_DATA_PATH = ROOT / "stage2_training_data.jsonl"

SCHEMA_PATH = ROOT / "stage2_llm_output_schema.json"
PROMPT_PATH = ROOT / "stage2_llm_prompt_v2.md"
TEST_CASES_PATH = ROOT / "stage2_llm_test_cases.jsonl"
TEST_SUMMARY_PATH = ROOT / "stage2_llm_test_cases_summary.md"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_schema(taxonomy: list[dict[str, Any]]) -> dict[str, Any]:
    l1_codes = [x["code"] for x in taxonomy]
    l1_names = [x["name"] for x in taxonomy]
    l2_codes = [l2["code"] for x in taxonomy for l2 in x.get("l2", [])]
    l2_names = sorted({l2["name"] for x in taxonomy for l2 in x.get("l2", [])})
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Stage 2 LLM Product/Service Category Classification Output",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "sample_id",
            "main_entity",
            "main_entity_type",
            "primary_category",
            "confidence",
            "needs_review",
            "review_flags",
            "evidence",
            "alternative_categories",
            "auxiliary",
            "notes",
        ],
        "properties": {
            "sample_id": {"type": "string", "description": "Input sample ID."},
            "main_entity": {
                "type": "string",
                "description": "被投诉的商品/服务主实体；必须来自原文，无法确定时输出 N/A。",
            },
            "main_entity_type": {"type": "string", "enum": ["PRODUCT", "SERVICE", "PLATFORM_SERVICE", "UNKNOWN"]},
            "primary_category": {
                "type": "object",
                "additionalProperties": False,
                "required": ["l1_code", "l1_name", "l2_code", "l2_name", "product_service_type"],
                "properties": {
                    "l1_code": {"type": "string", "enum": l1_codes},
                    "l1_name": {"type": "string", "enum": l1_names},
                    "l2_code": {"type": "string", "enum": l2_codes},
                    "l2_name": {"type": "string", "enum": l2_names},
                    "product_service_type": {"type": "string", "enum": ["PHYSICAL", "VIRTUAL", "LOCAL", "PLATFORM", "OTHER"]},
                },
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "needs_review": {
                "type": "boolean",
                "description": "仅表示模型不确定或品类边界风险，不代表要设计人工复核流程。",
            },
            "review_flags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "如 ENTITY_MISSING, TAXONOMY_GAP, APPLE_AMBIGUITY, WRONG_ITEM_CONTEXT, LOW_CONFIDENCE。",
            },
            "evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["text", "source_field", "supports"],
                    "properties": {
                        "text": {"type": "string"},
                        "source_field": {"type": "string", "enum": ["title", "content_summary", "merchant", "platform", "none"]},
                        "supports": {"type": "string", "enum": ["main_entity", "category", "brand", "exclusion", "ambiguity"]},
                    },
                },
            },
            "alternative_categories": {
                "type": "array",
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["l1_code", "l1_name", "l2_code", "l2_name", "reason"],
                    "properties": {
                        "l1_code": {"type": "string", "enum": l1_codes},
                        "l1_name": {"type": "string", "enum": l1_names},
                        "l2_code": {"type": "string", "enum": l2_codes},
                        "l2_name": {"type": "string", "enum": l2_names},
                        "reason": {"type": "string"},
                    },
                },
            },
            "auxiliary": {
                "type": "object",
                "additionalProperties": False,
                "required": ["brand", "complaint_issue", "service_context"],
                "properties": {
                    "brand": {"type": ["string", "null"], "description": "品牌辅助字段；不能替代 product category。"},
                    "complaint_issue": {"type": ["string", "null"], "description": "质量/退款/物流/客服等投诉问题，只作辅助。"},
                    "service_context": {"type": ["string", "null"], "description": "运费险、优惠券、账号、配送等服务上下文。"},
                },
            },
            "notes": {"type": "string"},
        },
    }


def taxonomy_markdown(taxonomy: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for l1 in taxonomy:
        lines.append(f"### {l1['code']} {l1['name']}")
        lines.append(f"- type: {l1.get('type', '')}")
        if l1.get("description"):
            lines.append(f"- 说明：{l1['description']}")
        lines.append("| L2 code | L2 name | examples |")
        lines.append("|---|---|---|")
        for l2 in l1.get("l2", []):
            examples = "、".join(l2.get("examples", [])[:8])
            lines.append(f"| {l2['code']} | {l2['name']} | {examples} |")
        lines.append("")
    return "\n".join(lines)


def build_prompt(taxonomy: list[dict[str, Any]]) -> str:
    example_output = {
        "sample_id": "S000",
        "main_entity": "手机",
        "main_entity_type": "PRODUCT",
        "primary_category": {
            "l1_code": "06",
            "l1_name": "数码电子",
            "l2_code": "06-01",
            "l2_name": "手机通讯",
            "product_service_type": "PHYSICAL",
        },
        "confidence": 0.93,
        "needs_review": False,
        "review_flags": [],
        "evidence": [{"text": "苹果手机iphone17", "source_field": "content_summary", "supports": "main_entity"}],
        "alternative_categories": [],
        "auxiliary": {"brand": "Apple/苹果", "complaint_issue": "质量问题", "service_context": "售后检测"},
        "notes": "按被投诉主商品归类，不按售后问题归类。",
    }
    return f"""# Stage 2 LLM Product/Service Category Classification Prompt v2

## 0. 角色

你是电商投诉数据的商品/服务品类分类器。你的任务是从投诉标题、正文摘要、平台、商家等字段中识别“被投诉的商品或服务主实体”，并输出该实体所属的商品/服务品类 L1/L2。

重要：本任务不是投诉问题分类。不要把“退款、物流、客服、质量、虚假宣传、售后”等投诉问题当成商品品类。它们只能作为辅助字段 `auxiliary.complaint_issue` 或 `auxiliary.service_context`。

## 1. 当前项目口径

- 主目标：商品/服务品类分类，即 `primary_category.l1_code/l1_name/l2_code/l2_name`。
- 品牌识别是辅助维度，不能替代品类。例如 iPhone、iPad 可辅助识别 Apple，但品类仍应分别是手机通讯/平板电脑等商品品类。
- 当前阶段暂不扩展人工复核流程。`needs_review` 只表示模型不确定或边界风险，用于离线分析。
- 输出必须是单个合法 JSON 对象，不要输出 Markdown，不要解释 JSON 之外的内容。

## 2. 输入字段

```json
{{
  "sample_id": "S000",
  "platform": "抖音商城",
  "merchant": "某某旗舰店",
  "title": "投诉标题",
  "content_summary": "投诉正文摘要"
}}
```

## 3. 分类原则

1. 先找主实体，再分类。主实体必须是被投诉的商品/服务本体。
2. 购买商品与收到错发物冲突时，优先按“购买的商品”分类；错发物只放 notes 或 auxiliary。
3. 售后、退款、客服、物流只是问题/场景，不是商品品类；除非投诉对象本身就是平台服务、账号、配送服务、优惠券、会员等服务。
4. 品牌和型号用于辅助推断品类，但 evidence 必须能回到原文。
5. 不允许无来源实体。比如原文没有“水性笔”，就不能输出水性笔。
6. 遇到歧义词要用上下文消歧：
   - “苹果手机 / iPhone / Pro Max”通常是 `06 数码电子 > 06-01 手机通讯`。
   - “昭通苹果 / 烂苹果 / 生鲜苹果”通常是 `01 食品生鲜 > 01-04 生鲜水果`。
   - “手机号 / 绑定手机 / 验证码手机”通常是账号上下文，不是手机商品。
   - “包邮、红包、表情包、包庇、包括、包装、包裹”里的“包”不是箱包。
   - “猫腻、天猫、挂羊头卖狗肉”里的猫/狗不是宠物。
   - “三包”不是箱包。
7. 如果无法找到商品/服务主实体，输出 `main_entity="N/A"`，分类到 `98 其他/待人工复核 > 98-01 暂无法归类`，并设置 `needs_review=true`、`review_flags=["ENTITY_MISSING"]`。
8. 如果实体存在但 taxonomy 没有合适 L2，优先选择最接近的 L2，同时设置 `needs_review=true`、`review_flags=["TAXONOMY_GAP"]`。

## 4. 输出 JSON 结构

输出必须符合文件 `stage2_llm_output_schema.json`。核心结构如下：

```json
{json.dumps(example_output, ensure_ascii=False, indent=2)}
```

字段要求：

- `main_entity`：被投诉主商品/服务，必须来自 title/content_summary/merchant/platform；无法确定为 `N/A`。
- `main_entity_type`：`PRODUCT`、`SERVICE`、`PLATFORM_SERVICE`、`UNKNOWN`。
- `primary_category`：必须来自下方 taxonomy，L1/L2 code 和 name 必须匹配。
- `confidence`：0 到 1。高置信建议 >=0.85；边界不清 0.5-0.75；无法分类 <=0.5。
- `needs_review`：边界不清、实体缺失、taxonomy gap、证据不足时为 true。
- `review_flags`：只作为风险标记，不展开人工流程。
- `evidence`：每条 evidence 的 text 必须是原文片段或原文字段中的明确词，不能编造。
- `auxiliary.brand`：品牌辅助字段；没有则 null。
- `auxiliary.complaint_issue`：质量/退款/物流/客服等问题辅助字段；没有则 null。
- `auxiliary.service_context`：运费险、优惠券、账号、配送等服务上下文；没有则 null。

## 5. Few-shot 示例

### 示例 A：苹果手机不是水果
输入：
```json
{{"sample_id":"S019","platform":"京东商城","merchant":"京东客服","title":"京东商城售后服务质量太差","content_summary":"购买苹果手机iphone17一台，收到货第二天发现锁屏按键失灵，商家要求返厂检测。"}}
```
输出：
```json
{{"sample_id":"S019","main_entity":"手机","main_entity_type":"PRODUCT","primary_category":{{"l1_code":"06","l1_name":"数码电子","l2_code":"06-01","l2_name":"手机通讯","product_service_type":"PHYSICAL"}},"confidence":0.94,"needs_review":false,"review_flags":[],"evidence":[{{"text":"苹果手机iphone17","source_field":"content_summary","supports":"main_entity"}}],"alternative_categories":[],"auxiliary":{{"brand":"Apple/苹果","complaint_issue":"质量问题","service_context":"售后检测"}},"notes":"苹果在手机型号上下文中按手机通讯分类。"}}
```

### 示例 B：账号绑定手机号不是手机商品
输入：
```json
{{"sample_id":"S929","platform":"唯品会","merchant":"唯品会","title":"唯品会账号用微信登绑别人信息，买东西后换绑遇难题！","content_summary":"账号绑定的别人手机还有地址，需要那个手机号的验证码，客服说没有解决办法。"}}
```
输出：
```json
{{"sample_id":"S929","main_entity":"账号","main_entity_type":"PLATFORM_SERVICE","primary_category":{{"l1_code":"20","l1_name":"平台服务与账号服务","l2_code":"20-01","l2_name":"账号服务","product_service_type":"PLATFORM"}},"confidence":0.88,"needs_review":false,"review_flags":[],"evidence":[{{"text":"账号","source_field":"title","supports":"main_entity"}},{{"text":"换绑","source_field":"title","supports":"category"}}],"alternative_categories":[],"auxiliary":{{"brand":null,"complaint_issue":"账号换绑问题","service_context":"手机号验证码"}},"notes":"手机号是账号验证上下文，不按手机通讯分类。"}}
```

### 示例 C：购买商品与错发物冲突
输入：
```json
{{"sample_id":"S679","platform":"抖音商城","merchant":"HAOYU服饰","title":"抖音HAOYU服饰虚假发货","content_summary":"下单米白色羽绒服，签收后包裹内是耳环而非所购羽绒服。"}}
```
输出：
```json
{{"sample_id":"S679","main_entity":"羽绒服","main_entity_type":"PRODUCT","primary_category":{{"l1_code":"02","l1_name":"服饰鞋包","l2_code":"02-01","l2_name":"女装","product_service_type":"PHYSICAL"}},"confidence":0.82,"needs_review":true,"review_flags":["GENDER_UNKNOWN","WRONG_ITEM_CONTEXT"],"evidence":[{{"text":"下单米白色羽绒服","source_field":"content_summary","supports":"main_entity"}},{{"text":"包裹内是耳环而非所购羽绒服","source_field":"content_summary","supports":"exclusion"}}],"alternative_categories":[],"auxiliary":{{"brand":null,"complaint_issue":"虚假发货/错发货","service_context":null}},"notes":"按购买商品羽绒服分类，耳环只是错发物。"}}
```

### 示例 D：确实无法判断主实体
输入：
```json
{{"sample_id":"S000","platform":"拼多多","merchant":"某店铺","title":"虚假宣传","content_summary":"商家一直拖延，客服不处理。"}}
```
输出：
```json
{{"sample_id":"S000","main_entity":"N/A","main_entity_type":"UNKNOWN","primary_category":{{"l1_code":"98","l1_name":"其他/待人工复核","l2_code":"98-01","l2_name":"暂无法归类","product_service_type":"OTHER"}},"confidence":0.35,"needs_review":true,"review_flags":["ENTITY_MISSING"],"evidence":[],"alternative_categories":[],"auxiliary":{{"brand":null,"complaint_issue":"虚假宣传/客服问题","service_context":null}},"notes":"文本没有足够商品或服务实体。"}}
```

## 6. Taxonomy：合法 L1/L2

{taxonomy_markdown(taxonomy)}

## 7. 最终任务

对每条输入投诉，只输出一个 JSON 对象。不要输出 Markdown，不要输出解释，不要输出多余文字。确保：

- L1/L2 code 和 name 来自 taxonomy 且互相匹配。
- evidence 必须来自原文。
- 主分类是商品/服务品类，不是投诉问题。
- 不确定时使用 `needs_review=true` 和合适的 `review_flags`，但仍尽量给出最接近的品类。
"""


def select_test_cases(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {r["sample_id"]: r for r in records}
    selected: list[tuple[dict[str, Any], str]] = []
    seen: set[str] = set()

    def add(record: dict[str, Any], focus: str) -> None:
        if record["sample_id"] in seen:
            return
        seen.add(record["sample_id"])
        selected.append((record, focus))

    must_include = [
        "S038",
        "S616",
        "S051",
        "S977",
        "S014",
        "S071",
        "S644",
        "S679",
        "S929",
        "S982",
        "S019",
        "S039",
        "S782",
        "S939",
    ]
    for sid in must_include:
        if sid not in by_id:
            continue
        if sid in {"S038", "S616"}:
            focus = "rule_mismatch_unsure"
        elif sid in {"S051", "S977"}:
            focus = "taxonomy_gap"
        elif sid in {"S019", "S039", "S982"}:
            focus = "corrected_boundary_case"
        elif sid in {"S644", "S679", "S929", "S071", "S014"}:
            focus = "boundary_exclusion_case"
        else:
            focus = "known_user_question_case"
        add(by_id[sid], focus)

    by_l1_review: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if (not record["rule"]["matched"]) and record["need_human_review"]:
            by_l1_review[record["label"]["l1_name"]].append(record)
    for l1_name in sorted(by_l1_review):
        add(sorted(by_l1_review[l1_name], key=lambda x: x["sample_id"])[0], "rule_unmatched_review_or_ambiguous")

    by_l2_auto: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if (not record["rule"]["matched"]) and record["use_for_weak_train"]:
            by_l2_auto[record["label"]["l2_code"]].append(record)
    for l2_code in sorted(by_l2_auto):
        if len(selected) >= 55:
            break
        add(sorted(by_l2_auto[l2_code], key=lambda x: x["sample_id"])[0], "rule_unmatched_auto_pass")

    l2_counts = Counter(r["label"]["l2_code"] for r in records if r["use_for_weak_train"])
    for record in sorted(records, key=lambda x: (l2_counts[x["label"]["l2_code"]], x["sample_id"])):
        if len(selected) >= 60:
            break
        if record["use_for_weak_train"] and l2_counts[record["label"]["l2_code"]] <= 3:
            add(record, "long_tail_l2")

    test_rows = []
    for record, focus in selected[:60]:
        test_rows.append(
            {
                "sample_id": record["sample_id"],
                "test_focus": focus,
                "input": {
                    "sample_id": record["sample_id"],
                    "platform": record["platform"],
                    "merchant": record["merchant"],
                    "title": record["title"],
                    "content_summary": record["content_summary"],
                },
                "reference_label": record["label"],
                "reference_main_entity": record["main_entity"],
                "label_quality": record["label_quality"],
                "rule_context": record["rule"],
            }
        )
    return test_rows


def write_test_summary(test_rows: list[dict[str, Any]]) -> None:
    focus_counts = Counter(x["test_focus"] for x in test_rows)
    l1_counts = Counter(x["reference_label"]["l1_name"] for x in test_rows)
    lines = [
        "# Stage 2 LLM Test Cases Summary",
        "",
        "## 1. 文件",
        "",
        "- 测试集：`stage2_llm_test_cases.jsonl`",
        "- Prompt：`stage2_llm_prompt_v2.md`",
        "- 输出 schema：`stage2_llm_output_schema.json`",
        "",
        "## 2. 抽样目的",
        "",
        "该测试集用于验证 LLM 兜底分类器，不用于人工复核流程扩展。样本优先覆盖规则未命中、规则分歧、taxonomy gap、边界排除和长尾 L2。",
        "",
        "## 3. 总体统计",
        "",
        f"- 样本数：{len(test_rows)}",
        f"- 覆盖 L1：{len(l1_counts)}",
        "",
        "## 4. test_focus 分布",
        "",
        "| focus | count |",
        "|---|---:|",
    ]
    for key, value in focus_counts.most_common():
        lines.append(f"| {key} | {value} |")
    lines.extend(["", "## 5. L1 分布", "", "| L1 | count |", "|---|---:|"])
    for key, value in l1_counts.most_common():
        lines.append(f"| {key} | {value} |")
    lines.extend(
        [
            "",
            "## 6. 使用方式",
            "",
            "1. 将 `stage2_llm_prompt_v2.md` 作为系统/开发提示词。",
            "2. 将 `stage2_llm_test_cases.jsonl` 每行的 `input` 对象逐条发送给模型。",
            "3. 模型输出必须是单个 JSON 对象，并用 `stage2_llm_output_schema.json` 或 `stage2_validate_llm_outputs.py` 校验。",
            "4. 用 `reference_label` 做离线比较；不要把 reference_label 发给模型。",
        ]
    )
    TEST_SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    taxonomy = load_json(TAXONOMY_PATH)
    records = load_jsonl(TRAINING_DATA_PATH)
    SCHEMA_PATH.write_text(json.dumps(build_schema(taxonomy), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    PROMPT_PATH.write_text(build_prompt(taxonomy), encoding="utf-8")
    test_rows = select_test_cases(records)
    TEST_CASES_PATH.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in test_rows) + "\n",
        encoding="utf-8",
    )
    write_test_summary(test_rows)
    print(f"wrote {SCHEMA_PATH.name}")
    print(f"wrote {PROMPT_PATH.name}")
    print(f"wrote {TEST_CASES_PATH.name}: {len(test_rows)} rows")
    print(f"wrote {TEST_SUMMARY_PATH.name}")


if __name__ == "__main__":
    main()
