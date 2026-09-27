---
name: maoxuan-skills-system
description: |
  《毛泽东选集》原文检索 + 方法论原子 Skills + 高层框架 + 组合工作流的统一入口。
  原文/出处问题走 retrieval；通用方法问题走 framework -> atomic skills；复杂任务走 composite skills。
  必须区分原文、解释和现代迁移，必要时绑定本仓库毛选md证据。
---

# Maoxuan Skills System Router

## 0. 先分类任务

### A. SOURCE_LOOKUP
用户主要在问：原文、出处、文章内容、概念在文本中的出现、不同文章的表述差异。

执行：
1. 使用 `retrieval/search.py` 或直接读取 `毛选md/`。
2. 给出文章名、卷次、Source ID/路径。
3. 解释必须与原文分开。
4. 不需要为了“显得会分析”强行调用方法论 Skill。

### B. METHOD_APPLICATION
用户要把《毛选》中的分析方法用于科研、产品、工程、组织、个人决策等非政治问题。

执行：
1. 先读取 `skills/frameworks/FRAMEWORKS.json` 选择一个高层框架。
2. 再读取 `skills/atomic/CATALOG.json`，只选择必要的 1–4 个 Atomic Skills。
3. 如果 `vendor/kangarooking/.../SKILL.md` 已同步，读取完整 Skill 的触发、执行和边界。
4. 输出时明确标识“方法迁移/类比”，不要把现代案例写成原文结论。

### C. COMPOSITE_TASK
用户面对复杂、跨阶段任务，如“先调查再判断再执行”“完整诊断一个组织问题”。

执行：
- 读取 `skills/composite/` 中最匹配的工作流；
- Composite 只决定调用顺序和判停条件；
- 每一步仍由 Atomic Skill 的边界约束。

### D. MIXED
既要原文依据，又要方法应用。

顺序必须是：
`Retrieval -> Evidence -> Interpretation -> Transfer -> Atomic/Composite Execution`。

## 1. 高层框架

见 `skills/frameworks/FRAMEWORKS.json`。框架用于规划，不替代 Atomic Skill。

## 2. 原子 Skill

见 `skills/atomic/CATALOG.json`。完整上游内容由：

```bash
python3 scripts/sync_upstreams.py
```

同步到 `vendor/kangarooking/`，版本由 `upstream/UPSTREAM_LOCK.json` 锁定。

## 3. 证据约束

当回答包含“原文认为/文中说/毛泽东在某文中提出”等可核查断言时：

1. 优先检索本仓库 `毛选md/`；
2. 使用 `evidence/skill-source-map.generated.json`（若已生成）；
3. 没找到时降低表述强度：使用“该 Skill 将其解释为……”而不是声称原文明确如此表述。

## 4. 组合约束

- 默认最多 4 个 Atomic Skills。
- 信息明显不足时，优先回到 `diaocha-yanjiu` / retrieval，而不是继续抽象推理。
- 多个 Skill 给出冲突方向时，先检查适用条件与历史/现代情境差异，不做机械多数表决。
- 涉及高代价现实决策时，输出假设、证据缺口和判停条件。

## 5. 安全与政治中立

- 不把历史军事技巧转化为现实暴力行动指导。
- 对现实政治人物、党派、选举、政策选择，不使用本系统替用户做政治选择或提供影响特定政治选择的策略；可做来源检索、历史解释和中性事实比较。
- 不以“角色扮演毛泽东”的方式冒充本人观点；允许描述“某上游 Skill 的风格化表达”，但默认使用分析型、可溯源表达。
