---
name: research-and-decision
description: 研究与决策闭环；通过多个原子 Skill 的有序组合完成复杂任务。
atomic_skills: ["diaocha-yanjiu", "shishiqiushi-sigao", "maodun-fenxi", "maodun-techuxing", "shijian-renshilun"]
---

# 研究与决策闭环

适用于：信息不完整、存在多个解释、又需要形成可验证决策的问题。

## Workflow
1. **调查研究**：列出关键未知项与一手证据缺口。信息不足时不得跳过。
2. **信息加工**：区分事实、推断、噪声与冲突证据。
3. **矛盾分析**：识别当前真正限制目标的主要问题。
4. **特殊性检查**：确认拟采用的方法适用于当前情境，而不是照搬模板。
5. **实践验证**：把结论转成最小可验证行动，并定义反馈信号。

## Stop conditions
- 已有高质量一手数据且问题只需简单计算：不要强行调用全部步骤。
- 关键证据无法获得：输出不确定性和下一步取证计划，而不是编造结论。

## Evidence rule
若回答声称某一步直接来自具体原文，应通过 `retrieval/` 或 `evidence/` 核验；否则表述为“本项目基于上游 Skill 做的现代迁移”。
