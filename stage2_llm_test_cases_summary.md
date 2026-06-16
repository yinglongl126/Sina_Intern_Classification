# Stage 2 LLM Test Cases Summary

## 1. 文件

- 测试集：`stage2_llm_test_cases.jsonl`
- Prompt：`stage2_llm_prompt_v2.md`
- 输出 schema：`stage2_llm_output_schema.json`

## 2. 抽样目的

该测试集用于验证 LLM 兜底分类器，不用于人工复核流程扩展。样本优先覆盖规则未命中、规则分歧、taxonomy gap、边界排除和长尾 L2。

## 3. 总体统计

- 样本数：60
- 覆盖 L1：19

## 4. test_focus 分布

| focus | count |
|---|---:|
| rule_unmatched_auto_pass | 23 |
| long_tail_l2 | 20 |
| boundary_exclusion_case | 5 |
| corrected_boundary_case | 3 |
| rule_unmatched_review_or_ambiguous | 3 |
| rule_mismatch_unsure | 2 |
| taxonomy_gap | 2 |
| known_user_question_case | 2 |

## 5. L1 分布

| L1 | count |
|---|---:|
| 服饰鞋包 | 10 |
| 平台服务与账号服务 | 7 |
| 数码电子 | 6 |
| 家居家装 | 5 |
| 食品生鲜 | 4 |
| 图书文娱与文创 | 3 |
| 其他/待人工复核 | 3 |
| 运动户外 | 3 |
| 本地生活服务 | 3 |
| 美妆个护 | 3 |
| 家用电器 | 2 |
| 医药健康 | 2 |
| 汽车用品 | 2 |
| 珠宝饰品与奢侈品 | 2 |
| 宠物用品 | 1 |
| 虚拟商品与数字服务 | 1 |
| 教育培训服务 | 1 |
| 金融支付与保险服务 | 1 |
| 母婴用品 | 1 |

## 6. 使用方式

1. 将 `stage2_llm_prompt_v2.md` 作为系统/开发提示词。
2. 将 `stage2_llm_test_cases.jsonl` 每行的 `input` 对象逐条发送给模型。
3. 模型输出必须是单个 JSON 对象，并用 `stage2_llm_output_schema.json` 或 `stage2_validate_llm_outputs.py` 校验。
4. 用 `reference_label` 做离线比较；不要把 reference_label 发给模型。
