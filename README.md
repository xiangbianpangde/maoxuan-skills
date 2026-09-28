# maoxuan-skills

一个分层的《毛泽东选集》方法论 Skill System。项目不把三套现有工作简单复制到同一目录，而是把它们分别放到最合适的层，并以本仓库现有的 `毛选md/` 作为唯一原文事实源。

## 架构

```text
用户问题
   │
   ▼
SKILL.md / Router
   ├── 原文、出处、概念解释 ──> retrieval/ ──> 毛选md/
   ├── 方法应用 ─────────────> Framework Router
   │                              │
   │                              ├── 7 个高层框架（leezythu 基线）
   │                              └── 25 个原子 Skill（kangarooking 基线）
   │
   └── 复杂任务 ─────────────> Composite Skills
                                  │
                                  └── 多个 Atomic Skill 的有序组合

所有需要引用原文的回答
   └── evidence/ 绑定回本仓库 corpus
```

### 三个上游分别承担什么

1. **`kangarooking/mao-selected-works-skill`**：25 个经过验证的原子方法论 Skill，作为 Atomic Skill baseline。
2. **`leezythu/maoxuan-skill`**：7 个高层心智模型与总体分析入口，作为 Framework/Planner baseline。
3. **`henryczq/mao-selected-works-skill`**：本地全文检索、关键词/向量/重排的工程思路。由于该仓库当前未在根目录声明可复用许可证，本项目不复制其代码或语料，而是独立实现兼容的 Retrieval Layer。

上游版本全部锁定在 `upstream/UPSTREAM_LOCK.json`。

## 本仓库新增的部分

- `SKILL.md`：统一总入口和路由约束。
- `skills/atomic/CATALOG.json`：25 个原子 Skill 的规范化目录。
- `skills/frameworks/FRAMEWORKS.json`：7 个高层框架与 Atomic Skill 映射。
- `skills/composite/`：研究决策、复杂问题分析、非暴力战略分析、组织改进四个组合 Skill。
- `skills/runtime/`：紧凑 Runtime Cards、Planner Contract 与可靠性策略。
- `retrieval/`：对 `毛选md/` 建立稳定 Source ID、SQLite 索引、关键词/可选向量/可选重排检索。
- `evidence/`：把 Skill 中的来源与引用绑定回本地 corpus。
- `eval/`：Routing / Fidelity / Citation / Composition / Task Gain 的评测与冻结实验。
- `.gitmodules` + `vendor/`：以 Git submodule 固定两个 MIT 上游 commit，避免复制漂移；`scripts/sync_upstreams.py` 负责初始化并校验版本。

## 运行时实证状态

截至 Task Gain v4，项目已经用冻结 held-out 对自动 Runtime 注入做了完整归因实验。最终证据不支持把毛选 Method Cards 作为现代任务的默认自动注入层，但支持通用的 Planner → Executor 作为复杂任务候选路径。

MiniMax M3 的 v4 结果：

- Vanilla：`87.969`
- Generic Planner：`97.383`
- Method Planner：`94.922`
- Generic Planner − Vanilla：`+9.414`，95% CI `[+5.469, +13.320]`
- Method Planner − Generic Planner：`-2.461`，95% CI `[-5.586, +0.586]`

因此当前推荐运行策略是：

```text
原文 / 出处 / 历史解释
    -> Retrieval + Evidence

简单或对延迟/成本敏感的现代任务
    -> Vanilla direct

复杂、多约束、需要阶段决策与回滚的现代任务
    -> Generic Planner -> Executor

用户显式要求使用、比较或研究某个毛选方法
    -> Router -> 可选 Runtime Card(s)
```

`Method Cards` 继续作为可解释的方法库、显式调用能力和研究对象保留，但项目**不宣称自动 Method-Card 注入普遍优于强模型的通用规划**。

最终实验报告见 `eval/reports/minimax-m3-task-gain-v4-final.md`。Raw `SKILL.md` 自动注入路线已废弃；Task Gain 自动注入调参线在 v4 后结项，不继续用 v5/v6 针对同一结果反复调提示词。

## 快速开始

```bash
# 推荐：首次克隆时直接拉取固定版本的两个上游
git clone --recurse-submodules https://github.com/xiangbianpangde/maoxuan-skills.git
cd maoxuan-skills

# 若已经普通 clone：初始化并校验 submodule
python3 scripts/sync_upstreams.py

# 2. 为本仓库现有毛选 Markdown 建索引
python3 retrieval/build_index.py

# 3. 检索原文
python3 retrieval/search.py search "没有调查就没有发言权"

# 4. 建立 Skill -> 原文证据映射
python3 scripts/build_evidence_map.py

# 5. 静态验收
python3 eval/run_static_checks.py
```

如果需要可选 embedding + reranker：

```bash
cp retrieval/config.example.json retrieval/config.json
export MAOXUAN_API_KEY='...'
python3 retrieval/build_index.py --embeddings
python3 retrieval/search.py hybrid "主要矛盾如何判断"
```

默认配置兼容 OpenAI-style `/embeddings` 接口和常见 `/rerank` 接口；密钥只从环境变量读取。

## 运行原则

### 1. Source 与 Transfer 分层

Agent 必须区分：

- **Source**：原文实际上说了什么；
- **Interpretation**：方法论抽象；
- **Transfer**：把方法迁移到科研、产品、工程、管理等新场景后的适配；
- **Evidence**：原文依据。

不得把现代商业/工程经验反向伪装成原文观点。

### 2. 原文问题优先 Retrieval

“这句话出自哪里”“这篇文章讲什么”“原文如何表述”等问题，不应先调用方法论 Skill，而应检索 `毛选md/`。

### 3. 现代复杂任务默认使用通用规划，方法库按需调用

Task Gain v4 已证明 Generic Planner 相比 Vanilla 有明显增益，但没有证明自动 Method-Card 注入在 Generic Planner 之上还有额外增益。因此现代复杂任务默认走通用 Planner → Executor；Framework / Atomic / Composite 层用于显式方法应用、研究、解释和可控实验，不因关键词命中而自动堆叠大量 Skill。

### 4. 组合 Skill 只负责顺序与判停

Composite Skill 不重新发明方法，而是明确：什么时候调用哪个 Atomic Skill、何时停止、何时回退到调查和原文核验。它属于可选方法库，不是所有复杂任务的默认前置层。

### 5. 边界

本项目定位为文本研究与通用问题分析工具：

- 历史军事来源的方法只允许迁移到非暴力的资源配置、竞争、项目管理等场景；不提供现实暴力行动规划。
- 对现实政治、选举或公共政策选择，系统应提供来源、事实和中性比较，而不替用户做政治选择或用策略模块进行说服性影响。
- 若原文证据不足，明确标记为解释或迁移，不伪造出处。

## 上游与许可

两个以 Git submodule 固定在 `vendor/` 的方法论上游均为 MIT，许可证副本保存在 `upstream/licenses/`。`henryczq/mao-selected-works-skill` 仅作为检索架构参考，不复制其未明确许可的代码或语料。

本仓库 `毛选md/` 的文本来源和再分发许可应由仓库维护者单独核验；本项目不会用一个总 MIT License 覆盖第三方文本语料。
