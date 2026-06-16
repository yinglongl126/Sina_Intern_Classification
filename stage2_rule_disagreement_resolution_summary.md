# Stage 2 Rule Disagreement Resolution Summary

## 1. 输入

- 来源文件: `outputs/rule_review/stage2_rule_disagreement_review_25.xlsx`
- 分歧样本: 25 条
- 裁决分布: RULE_OK 18, LABEL_OK 4, UNSURE 2, BOTH_WRONG 1

## 2. 已回写到 500 条弱标签的样本

- RULE_OK: S019, S036, S039, S058, S065, S077, S685, S688, S735, S754, S772, S787, S799, S817, S833, S851, S946, S992
- BOTH_WRONG: S982, 修正为 `图书文娱与文创 > 文具与乐器`, 主实体 `AI智慧钢琴`

## 3. 保持原弱标签不变的样本

- LABEL_OK: S071, S644, S679, S929
- UNSURE: S038, S616

## 4. 回写后主表状态

- 主 CSV 行数: 500
- need_human_review=TRUE: 168
- need_human_review=FALSE: 332
- taxonomy_gap_candidate=TRUE: 2
- review cases 文件行数: 168
- gap candidates 文件行数: 2

## 5. 后续规则收紧点

- S071: `帽子处` 只是衣服部位描述，不应触发服饰配饰。
- S644: `运费险` 是辅助服务线索，不应覆盖一加手机。
- S679: `包裹内是耳环` 是错发物，不应覆盖购买的羽绒服。
- S929: 账号换绑场景中的手机号不应触发手机通讯。
