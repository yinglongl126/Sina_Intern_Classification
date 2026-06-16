# Sina Intern Classification

电商投诉商品/服务品类自动分类与分流系统原型。

本项目目标不是识别“投诉问题类型”（例如退款、物流、客服、质量问题），而是识别一条投诉涉及的**商品或服务品类**，用于后续统计、分流、治理和模型训练。

## 项目目标

给定一条电商投诉记录：

- 平台
- 商家
- 投诉标题
- 投诉正文摘要

系统需要识别：

- 被投诉的主商品/服务实体
- L1 商品/服务大类
- L2 商品/服务细类
- 品牌、投诉问题、服务上下文等辅助字段
- 分类置信度与边界风险标记

当前阶段聚焦 L1/L2 分类，不扩展人工复核流程。

## 当前进展

### Stage 1：品类体系与试标

- 建立 21 个 L1、114 个 L2 的商品/服务 taxonomy
- 完成 500 条投诉样本的 L1/L2 试标与多轮清洗
- 修复中文词边界误触发，例如：
  - `包` 被误识别为箱包
  - `猫腻` 被误识别为宠物猫
  - `手机号` 被误识别为手机商品
  - `运费险` 覆盖真实商品实体

### Stage 2：规则、ML 与 LLM 方案

- 已实现 Layer 0 规则引擎
- 已生成商品/服务词典和排除词典
- 已生成 ML/LLM 共用训练数据结构
- 已实现纯标准库轻量 ML baseline
- 已生成 LLM Prompt v2、输出 schema 和测试集

当前关键指标：

| 模块 | 指标 |
|---|---:|
| Layer 0 规则命中 | 259/500 |
| Layer 0 L1/L2 弱标签一致性 | 257/259 |
| 弱训练样本 | 332/500 |
| Char NB baseline L1 | 33.8% |
| Char NB baseline L2 | 22.4% |
| Hybrid baseline L1 | 81.0% |
| Hybrid baseline L2 | 76.3% |

说明：当前指标基于弱标签离线验证，不等同于最终人工金标准准确率。

## 核心文件

### 设计文档

| 文件 | 说明 |
|---|---|
| `project_overview.md` | 项目概述 |
| `category_taxonomy_design.md` | 品类体系设计 |
| `entity_extraction_design.md` | 实体抽取设计 |
| `brand_mapping_design.md` | 品牌识别设计 |
| `classification_rules.md` | 分类规则设计 |
| `model_strategy.md` | 模型策略 |
| `stage2_ai_ml_classification_plan.md` | Stage 2 AI/ML 总体方案 |

### Taxonomy 与词典

| 文件 | 说明 |
|---|---|
| `stage1_taxonomy.json` | L1/L2 品类体系 |
| `stage1_brand_mapping_seed.json` | 品牌词典种子 |
| `stage2_product_dictionary.json` | 商品/服务词典 |
| `stage2_exclusion_dictionary.json` | 排除词/上下文词典 |

### 规则与模型脚本

| 文件 | 说明 |
|---|---|
| `stage2_rule_engine.py` | Layer 0 规则引擎 |
| `stage2_prepare_training_data.py` | 生成 ML/LLM 训练数据 |
| `stage2_ml_baseline.py` | 轻量 ML baseline |
| `stage2_generate_llm_assets.py` | 生成 LLM prompt/schema/test cases |
| `stage2_validate_llm_outputs.py` | 校验 LLM 输出 |

### LLM 资产

| 文件 | 说明 |
|---|---|
| `stage2_llm_prompt_v2.md` | LLM 分类 Prompt v2 |
| `stage2_llm_output_schema.json` | LLM 输出 JSON schema |
| `stage2_llm_test_cases_summary.md` | LLM 测试集摘要 |

注意：`stage2_llm_test_cases.jsonl` 默认不提交，因为其中包含样本标题和正文摘要。

## 快速开始

进入项目目录：

```powershell
cd "D:\Sina Intern\Classifiction"
```

### 1. 运行规则引擎验证

```powershell
python stage2_rule_engine.py build-assets
python stage2_rule_engine.py validate
```

生成：

- `stage2_product_dictionary.json`
- `stage2_exclusion_dictionary.json`
- `stage2_rule_validation_report.md`

### 2. 生成训练数据

```powershell
python stage2_prepare_training_data.py
```

生成：

- `stage2_training_data.jsonl`
- `stage2_training_data_summary.md`

其中 `stage2_training_data.jsonl` 默认不提交到 GitHub。

### 3. 运行轻量 ML baseline

```powershell
python stage2_ml_baseline.py
```

生成：

- `stage2_ml_baseline_report.md`
- `stage2_ml_baseline_predictions.jsonl`

其中 predictions 默认不提交到 GitHub。

### 4. 生成 LLM Prompt 与测试资产

```powershell
python stage2_generate_llm_assets.py
```

生成：

- `stage2_llm_prompt_v2.md`
- `stage2_llm_output_schema.json`
- `stage2_llm_test_cases.jsonl`
- `stage2_llm_test_cases_summary.md`

### 5. 校验 LLM 输出

假设模型输出文件为 `deepseek_outputs.jsonl`：

```powershell
python stage2_validate_llm_outputs.py deepseek_outputs.jsonl
```

输出应为一行一个 JSON 对象，并符合 `stage2_llm_output_schema.json`。

## 混合分类架构

当前设计采用四层漏斗：

1. **Layer 0：规则/词典**
   - 高精度、可解释
   - 适合稳定高频品类

2. **Layer 1：轻量 ML / 后续 MacBERT**
   - 处理规则未覆盖但模式较稳定的样本
   - 当前已有 Char NB baseline

3. **Layer 2：LLM 兜底**
   - 处理长尾、歧义、复杂上下文
   - 使用 `stage2_llm_prompt_v2.md`

4. **Review flag**
   - 仅标记不确定性和边界风险
   - 当前阶段不扩展人工复核流程

## 数据与隐私说明

本仓库默认不提交以下内容：

- 原始投诉 Excel 数据
- 样本级 CSV/JSONL 明细
- 训练数据 JSONL
- 预测明细
- 本地 Excel 审查文件
- 缓存和临时文件

这些内容已写入 `.gitignore`。如果需要复现实验，请在本地保留原始数据文件，并按脚本生成相应中间产物。

## 目录说明

```text
.
├── stage1_taxonomy.json
├── stage2_rule_engine.py
├── stage2_prepare_training_data.py
├── stage2_ml_baseline.py
├── stage2_generate_llm_assets.py
├── stage2_validate_llm_outputs.py
├── stage2_ai_ml_classification_plan.md
├── stage2_llm_prompt_v2.md
├── stage2_llm_output_schema.json
├── *_design.md
├── *_summary.md
└── data/                  # ignored, raw/internal data
```

## 后续计划

- 扩展 1000 条弱标签数据
- 建设品牌-型号到品类的映射库
- 引入 TF-IDF + Logistic Regression baseline
- 在数据量足够后尝试 MacBERT 微调
- 对 LLM 测试集输出进行离线比较
- 再决定是否进入人工准确率评估阶段

