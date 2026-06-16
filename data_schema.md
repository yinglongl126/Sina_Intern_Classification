# 数据Schema设计（第二版 — 双维度结构）

## 0. 版本说明

第二版的核心变化：
1. **明确双维度结构：** product_category（主维度）+ complaint_issue（辅助维度）严格分离
2. **实体抽取结果前置：** detected_product_entities 作为分类的基础
3. **L3改为可选：** 阶段一以L1/L2为主，L3字段可为空
4. **human_review 字段更细化：** 明确触发原因代码

---

## 1. 系统输出JSON（双维度结构）

每条投诉完成处理后，输出以下JSON：

```json
{
  "complaint_id": "17390890267",
  "processed_at": "2025-12-06T00:01:04.000+08:00",

  "product_category": {
    "l1_code": "06",
    "l1_name": "数码电子",
    "l2_code": "06-02",
    "l2_name": "电脑整机与硬件",
    "l3_code": null,
    "l3_name": null,
    "l3_note": "阶段一暂不拆L3",
    "confidence": 0.88,
    "classification_basis": "标题和正文均明确提及'显卡'，型号5090指向NVIDIA显卡"
  },

  "product_service_type": "PHYSICAL",

  "detected_product_entities": {
    "extraction_status": "SUCCESS",
    "primary_entity": {
      "text": "5090显卡",
      "normalized": "显卡",
      "type": "PRODUCT",
      "source_field": "标题",
      "confidence": 0.95
    },
    "secondary_entities": [
      {
        "text": "显示器",
        "normalized": "显示器",
        "type": "PRODUCT",
        "relation": "关联设备"
      }
    ],
    "all_entities": [
      {"text": "5090显卡", "type": "PRODUCT", "field": "标题"},
      {"text": "淘宝", "type": "PLATFORM", "field": "内容"},
      {"text": "24370", "type": "AMOUNT", "field": "金额"}
    ]
  },

  "brand_info": {
    "main_brand": {
      "brand_id": "BRAND_NVIDIA",
      "normalized_brand": "NVIDIA/英伟达",
      "raw_mentions": ["5090"],
      "confidence": 0.90
    },
    "detected_brands": [
      {
        "raw_text": "5090",
        "normalized_brand": "NVIDIA/英伟达",
        "brand_id": "BRAND_NVIDIA",
        "brand_alias_type": "product_line",
        "confidence": 0.90,
        "source_field": "标题",
        "evidence_text": "5090显卡"
      }
    ],
    "brand_group": "NVIDIA Corporation",
    "sub_brand": null,
    "product_line": "GeForce RTX 50系列",
    "need_brand_review": false,
    "brand_review_reason": null
  },

  "complaint_issue": {
    "issue_type": "质量问题",
    "source": "问题字段",
    "is_auxiliary": true,
    "note": "此为辅助标签，不属于商品/服务品类维度"
  },

  "routing": {
    "target_team": "数码电子运营组",
    "priority": "MEDIUM",
    "basis": "基于商品品类L1=数码电子分流"
  },

  "need_human_review": false,
  "human_review_reason": null,

  "new_category_candidate": false,
  "new_category_suggestion": null,

  "model_info": {
    "classification_layer": "LAYER_2",
    "classification_model": "claude-opus-4-8",
    "entity_extraction_method": "LLM_NER",
    "entity_extraction_model": "claude-opus-4-8"
  },

  "processing_duration_ms": 1850
}
```

---

## 2. 无商品实体时的输出示例

```json
{
  "complaint_id": "17390890XXX",
  "processed_at": "2025-12-06T10:30:00.000+08:00",

  "product_category": {
    "l1_code": "98",
    "l1_name": "其他/待人工复核",
    "l2_code": "98-01",
    "l2_name": "暂无法归类",
    "l3_code": null,
    "l3_name": null,
    "confidence": 0.0
  },

  "product_service_type": "OTHER",

  "detected_product_entities": {
    "extraction_status": "FAILED",
    "failure_reason": "NO_PRODUCT_ENTITY_FOUND",
    "failure_detail": "标题:'要求退款'，内容:'等了一个月还没退'。仅包含投诉问题词，无商品/服务描述。",
    "primary_entity": null,
    "secondary_entities": [],
    "all_entities": [
      {"text": "拼多多", "type": "PLATFORM", "field": "服务名称"}
    ]
  },

  "brand_info": {
    "main_brand": null,
    "detected_brands": [],
    "brand_group": null,
    "sub_brand": null,
    "product_line": null,
    "need_brand_review": false,
    "brand_review_reason": "投诉中无品牌提及"
  },

  "complaint_issue": {
    "issue_type": "退款纠纷",
    "source": "标题+内容",
    "is_auxiliary": true
  },

  "routing": {
    "target_team": "人工复核队列",
    "priority": "HIGH",
    "basis": "无商品实体，无法按品类分流"
  },

  "need_human_review": true,
  "human_review_reason": "HR-4: 实体抽取失败，无商品/服务实体。标题和内容仅含投诉问题词(退款)，无商品描述。",

  "new_category_candidate": false,

  "model_info": {
    "classification_layer": "LAYER_3",
    "classification_model": "claude-opus-4-8",
    "entity_extraction_method": "LLM_NER",
    "entity_extraction_model": "claude-opus-4-8"
  },

  "processing_duration_ms": 2100
}
```

---

## 3. 字段详细说明

### 3.1 complaint_id
- **类型：** String，必填
- **说明：** 投诉单据唯一标识符

### 3.2 processed_at
- **类型：** ISO 8601 DateTime String，必填
- **说明：** 处理完成的时间戳

### 3.3 product_category（核心维度）
- **类型：** Object，必填
- **说明：** 商品/服务品类分类结果。**这是本项目的主输出。**
- **字段：**
  - `l1_code` / `l1_name` — 一级品类编码和名称，必填
  - `l2_code` / `l2_name` — 二级品类编码和名称，必填
  - `l3_code` / `l3_name` — 三级品类编码和名称。**阶段一可为null**，L3是可选字段
  - `l3_note` — L3为空时的说明（如"阶段一暂不拆L3"、"该L2下暂无L3"）
  - `confidence` — 品类分类置信度(0-1)
  - `classification_basis` — 分类依据的自然语言说明

### 3.4 product_service_type
- **类型：** Enum String，必填
- **可选值：** PHYSICAL / VIRTUAL / LOCAL / PLATFORM / OTHER
- **说明：** 投诉对象的宏观类型

### 3.5 detected_product_entities（前置模块输出）
- **类型：** Object，必填
- **说明：** 实体抽取模块的结果。**这是品类分类的前置输入。**
- **字段：**
  - `extraction_status` — "SUCCESS" 或 "FAILED"
  - `failure_reason` — 失败原因代码（仅status=FAILED时）
  - `primary_entity` — 主商品/服务实体对象
  - `secondary_entities` — 次要实体列表
  - `all_entities` — 所有抽取到的实体（包括平台、金额等非商品实体）
  - 详细格式见 `entity_extraction_design.md`

### 3.6 brand_info（辅助维度 — 品牌识别）

- **类型：** Object，可选（投诉中无品牌信息时可为 null）
- **说明：** 品牌识别与归一化结果。**品牌是辅助维度，不能替代 product_category。**
- **字段：**
  - `main_brand` — 主品牌对象（投诉主要涉及的品牌）
    - `brand_id` — 品牌唯一ID，如 `BRAND_APPLE`、`BRAND_HUAWEI`
    - `normalized_brand` — 归一化品牌名，格式 `English名/中文名`，如 `Apple/苹果`
    - `raw_mentions` — 原始文本中出现的品牌提及列表（可能包含产品线/型号）
    - `confidence` — 主品牌识别置信度（0-1）
  - `detected_brands` — 所有检测到的品牌提及列表（数组）
    - 每个元素包含：`raw_text`、`normalized_brand`、`brand_id`、`brand_alias_type`、`confidence`、`source_field`、`evidence_text`
    - `brand_alias_type` 可选值：`official_name`（官方名）、`chinese_name`（中文名）、`english_name`（英文名）、`product_line`（产品线）、`sub_brand`（子品牌）、`alias`（别名）、`abbreviation`（简称）
  - `brand_group` — 品牌集团（如"小米集团"、"Apple Inc."、"华为技术有限公司"），用于品牌聚合统计
  - `sub_brand` — 子品牌（如 Redmi/红米、荣耀/HONOR），如果投诉涉及子品牌则填充
  - `product_line` — 产品线/系列（如"iPhone"、"Mate"、"Galaxy S"），用于细化品牌内部分析
  - `need_brand_review` — Boolean，品牌识别结果是否需要人工复核
  - `brand_review_reason` — String 或 null，品牌人工复核触发原因

**品牌人工复核触发条件：**

| 编号 | 触发条件 | 说明 |
|------|---------|------|
| BR-1 | 品牌歧义词且上下文无法消歧 | 如"苹果"在无商品词上下文中无法判断是水果还是Apple |
| BR-2 | 多品牌提及且无法确定主品牌 | 如投诉中提到多个品牌 |
| BR-3 | 品牌与品类冲突 | 如"苹果水果"被识别为Apple品牌 |
| BR-4 | 疑似新品牌 | 品牌不在已知品牌词典中 |
| BR-5 | 品牌归一化低置信度（<0.70） | 品牌匹配不确定 |
| BR-6 | 只有品牌无商品词且品牌跨多品类 | 如"买了个小米" |

### 3.7 complaint_issue（辅助维度）
- **类型：** Object，可选
- **说明：** 投诉问题类型。**这是辅助维度，不等于商品品类。**
- **字段：**
  - `issue_type` — 问题类型（质量问题、退款纠纷、虚假宣传、发货问题、客服问题等）
  - `source` — 从哪个字段提取的
  - `is_auxiliary` — 固定为true，标记为辅助维度
  - `note` — 说明这是辅助标签
- **重要：** complaint_issue 字段仅作为辅助信息提供。系统分流**不基于此字段**，而是基于 product_category。

### 3.8 routing
- **类型：** Object，必填
- **说明：** 分流决策。**分流依据 product_category，而非 complaint_issue。**
- **字段：**
  - `target_team` — 推荐的处理团队
  - `priority` — HIGH / MEDIUM / LOW
  - `basis` — 分流依据的自然语言说明

### 3.9 need_human_review
- **类型：** Boolean，必填
- **说明：** 是否需要人工复核

### 3.10 human_review_reason
- **类型：** String 或 null
- **说明：** 触发人工复核的原因代码和描述（如"HR-4: 实体抽取失败..."）

### 3.11 new_category_candidate
- **类型：** Boolean，必填
- **说明：** 是否被标记为新品类候选

### 3.12 new_category_suggestion
- **类型：** Object 或 null
- **说明：** 新品类候选建议（仅当 new_category_candidate=true）

### 3.13 model_info
- **类型：** Object，必填
- **字段：**
  - `classification_layer` — 哪层做的最终分类（LAYER_0/1/2/3）
  - `classification_model` — 分类模型名称版本
  - `entity_extraction_method` — 实体抽取方法
  - `entity_extraction_model` — 实体抽取模型

### 3.14 processing_duration_ms
- **类型：** Integer，必填
- **说明：** 处理总耗时（毫秒）

---

## 4. 双维度结构设计说明

```
┌────────────────────────────────────────────┐
│            投诉分类结果                      │
│                                            │
│  ┌──────────────────────────────────────┐  │
│  │  product_category（主维度 — 本项目）   │  │
│  │  - L1/L2/L3 商品/服务品类             │  │
│  │  - 分流依据                          │  │
│  │  - 统计口径                          │  │
│  └──────────────────────────────────────┘  │
│                                            │
│  ┌──────────────────────────────────────┐  │
│  │  complaint_issue（辅助维度）          │  │
│  │  - 投诉问题类型（退款、质量等）        │  │
│  │  - 仅作参考，不用于分流               │  │
│  │  - is_auxiliary = true               │  │
│  └──────────────────────────────────────┘  │
│                                            │
│  ┌──────────────────────────────────────┐  │
│  │  routing（分流决策）                  │  │
│  │  - 基于 product_category 分流        │  │
│  │  - basis字段明确说明分流依据          │  │
│  └──────────────────────────────────────┘  │
└────────────────────────────────────────────┘
```

**为什么要严格分离？**

1. 如果"退款纠纷"被当成品类，那么一条"手机退款纠纷"和一条"衣服退款纠纷"会被分到同一个"品类"，失去了分流意义
2. 运营团队需要知道"我负责的品类有多少投诉"，而不是"退款问题有多少投诉"（后者可以独立统计）
3. 后续如果要接入12345体系，12345也是按行业领域（≈品类）分流，不是按投诉原因分流

---

## 5. 数据库表设计要点

### 5.1 主表核心字段

```sql
-- 品类分类（主维度）
l1_code, l1_name, l2_code, l2_name, l3_code, l3_name
product_service_type  -- PHYSICAL/VIRTUAL/LOCAL/PLATFORM/OTHER
category_confidence   -- 品类分类置信度

-- 实体抽取（前置模块）
entity_extraction_status  -- SUCCESS/FAILED
primary_entity_text       -- 主商品/服务实体文本
primary_entity_type       -- PRODUCT/BRAND/SERVICE/MODEL
entity_extraction_json    -- JSONB, 完整实体抽取结果

-- 品牌识别（辅助维度）
main_brand_id             -- 主品牌ID（如BRAND_APPLE）
main_brand_normalized     -- 主品牌归一化名称
main_brand_confidence     -- 主品牌置信度
brand_info_json           -- JSONB, 完整品牌识别结果
need_brand_review         -- BOOLEAN，品牌是否需要人工复核
brand_review_reason       -- 品牌人工复核原因代码（BR-1/BR-2/.../BR-6）

-- 投诉问题（辅助维度）
complaint_issue_type     -- 质量问题/退款纠纷/虚假宣传/... (可为null)
complaint_issue_source   -- 从哪个字段提取

-- 分流
routing_target           -- 分流目标团队
routing_priority         -- HIGH/MEDIUM/LOW
routing_basis            -- 分流依据

-- 人工复核
need_human_review        -- BOOLEAN
human_review_reason_code -- HR-1/HR-2/.../HR-10
human_review_reason      -- TEXT
review_status            -- PENDING/REVIEWED/ESCALATED
final_l1/l2/l3           -- 人工确认后的最终品类

-- 模型
classification_layer     -- LAYER_0/1/2/3
entity_extraction_method -- LLM_NER/DICTIONARY/BERT_NER
```

详细建表SQL保留第一版的表结构，新增上述字段。

---

## 6. API接口设计

### 6.1 分类接口（单条）

```
POST /api/v1/classify

Request:
{
  "complaint_id": "17390890267",
  "title": "买了两万多的显卡，温度过高一直黑屏不能使用",
  "content": "本人12月4号在淘宝购买了5090显卡...",
  "merchant": "阿里客服",
  "platform": "淘宝商城",
  "amount": 24370.0
}

Response:
{
  "code": 0,
  "data": { ... 完整分类结果JSON ... }
}
```

### 6.2 品类查询接口

```
GET /api/v1/categories?level=2&parent_code=06&stage=1

Response:
{
  "code": 0,
  "data": {
    "stage": 1,
    "categories": [
      { "code": "06-01", "name": "手机通讯", "l3_count": 0, "has_l3": false },
      ...
    ]
  }
}
```

### 6.3 统计接口（按品类维度）

```
GET /api/v1/stats/by-category?start_date=2025-12-01&end_date=2025-12-31&level=2

Response:
{
  "code": 0,
  "data": {
    "total": 24713,
    "distribution": [
      {"l2_code": "06-01", "l2_name": "手机通讯", "count": 1520, "percentage": 6.2},
      ...
    ],
    "unclassified_rate": 12.5  // 归入"其他/待人工复核"的比例
  }
}
```

### 6.4 统计接口（按问题类型维度 — 辅助）

```
GET /api/v1/stats/by-issue-type?start_date=2025-12-01&end_date=2025-12-31

Response:
{
  "code": 0,
  "data": {
    "note": "此为投诉问题类型统计（辅助维度），不是商品品类统计",
    "distribution": [
      {"issue_type": "质量问题", "count": 5200, "percentage": 21.0},
      {"issue_type": "退款纠纷", "count": 3800, "percentage": 15.4},
      ...
    ]
  }
}
```
