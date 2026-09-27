---
name: maoxuan-skills-system
description: |
  《毛泽东选集》原文检索 + 方法论原子 Skills + 高层框架 + 组合工作流的统一入口。
  原文/出处问题走 retrieval；真正需要方法论增益的问题走 framework -> atomic skills；复杂任务走 composite skills；普通任务可直接不调用本系统。
  必须区分原文、解释和现代迁移，必要时绑定本仓库毛选md证据。
---

# Maoxuan Skills System Router

## 0. 先做 Skill Necessity Gate

默认不是“遇到问题就调用毛选 Skill”。先判断本系统是否会带来**实质任务增益**。

### E. DIRECT / NO_SKILL
下列任务通常直接回答，不调用本系统：

- 普通教程、资源推荐、基础知识问答；
- 已经明确范围的计算、核对、格式化、简单实现；
- 单一且已知根因范围的 bug 修复；
- 配色、字体、排版等纯审美选择；
- 一次性的轻量偏好或琐碎争议；
- 其他不需要原文检索、方法论抽象或多阶段分析的请求。

原则：**能不用就不用，能用 1 个 Atomic Skill 就不用 3 个。**

## 1. 需要本系统时再分类任务

### A. SOURCE_LOOKUP
用户主要在问：原文、出处、文章内容、概念在文本中的出现、不同文章的表述差异。

执行：
1. 使用 `retrieval/search.py` 或直接读取 `毛选md/`。
2. 给出文章名、卷次、Source ID/路径。
3. 解释必须与原文分开。
4. 不需要为了“显得会分析”强行调用方法论 Skill。

### B. METHOD_APPLICATION
用户要把《毛选》中的分析方法用于科研、产品、工程、组织、个人决策等非政治问题，而且该方法能明显改善问题结构化、证据处理或决策过程。

执行：
1. 先读取 `skills/frameworks/FRAMEWORKS.json` 选择一个高层框架。
2. 再读取 `skills/atomic/CATALOG.json`，只选择必要的 1–4 个 Atomic Skills。
3. 使用 Catalog 的 `summary` 做初筛，再读取 `vendor/kangarooking/.../SKILL.md` 的完整触发、执行和边界；如果 submodule 尚未初始化，先执行 `python3 scripts/sync_upstreams.py`。
4. 输出时明确标识“方法迁移/类比”，不要把现代案例写成原文结论。

### C. COMPOSITE_TASK
用户面对复杂、跨阶段任务，如“先调查再判断再执行”“完整诊断一个组织问题”。

执行：
- 只有确实存在多个相互依赖阶段时才读取 `skills/composite/`；
- Composite 只决定调用顺序和判停条件；
- 每一步仍由 Atomic Skill 的边界约束。

### D. MIXED
既要原文依据，又要方法应用。

顺序必须是：
`Retrieval -> Evidence -> Interpretation -> Transfer -> Atomic/Composite Execution`。

## 2. 关键 Skill 冲突判别

- `shijian-renshilun`：核心是“行动 → 反馈 → 修正认识 → 再行动”；普通学习资源推荐不触发。
- `shishiqiushi-sigao`：核心是对杂乱/冲突/未验证材料做筛选、校验与综合；已经算好的数字复核、纯审美选择不触发。
- `maodun-fenxi`：核心是多个问题/力量之间找主要矛盾或当前瓶颈；单一明确 bug、琐碎偏好争议不触发。
- `maodun-techuxing`：核心是“方法必须匹配具体条件”；机械照搬行业标杆、模板，或原来有效的方法因环境变化失效时优先考虑。
- `diaocha-yanjiu`：核心是重大判断被一手事实缺口或未经验证假设阻塞；不是所有任务都默认“先调查”。

## 3. 高层框架

见 `skills/frameworks/FRAMEWORKS.json`。框架用于规划，不替代 Atomic Skill。

## 4. 原子 Skill

见 `skills/atomic/CATALOG.json`。完整上游内容以 Git submodule 固定在 `vendor/kangarooking/` 与 `vendor/leezythu/`。首次 clone 建议使用 `--recurse-submodules`；已有仓库可执行：

```bash
python3 scripts/sync_upstreams.py
```

脚本会初始化 submodule，并校验实际 HEAD 与 `upstream/UPSTREAM_LOCK.json` 完全一致。

## 5. 证据约束

当回答包含“原文认为/文中说/毛泽东在某文中提出”等可核查断言时：

1. 优先检索本仓库 `毛选md/`；
2. 使用 `evidence/skill-source-map.generated.json`（若已生成）；
3. 没找到时降低表述强度：使用“该 Skill 将其解释为……”而不是声称原文明确如此表述。

## 6. 组合约束

- 默认最多 4 个 Atomic Skills，优先最小充分集合。
- 信息明显不足且决策代价高时，才优先回到 `diaocha-yanjiu` / retrieval；不要把“需要更多信息”当成万能路由。
- 多个 Skill 给出冲突方向时，先检查适用条件与历史/现代情境差异，不做机械多数表决。
- 涉及高代价现实决策时，输出假设、证据缺口和判停条件。

## 7. 安全与政治中立

- 不把历史军事技巧转化为现实暴力行动指导。
- 对现实政治人物、党派、选举、政策选择，不使用本系统替用户做政治选择或提供影响特定政治选择的策略；可做来源检索、历史解释和中性事实比较。
- 不以“角色扮演毛泽东”的方式冒充本人观点；允许描述“某上游 Skill 的风格化表达”，但默认使用分析型、可溯源表达。
