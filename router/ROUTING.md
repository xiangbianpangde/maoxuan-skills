# Routing Contract

## 路由优先级

0. **Skill Necessity Gate**：先判断本系统是否有实质增益。普通教程/资源推荐、简单计算核对、单一明确 bug、纯审美选择、轻量偏好 → `direct`，不调用毛选 Skills。
1. **Source intent 优先**：出处、原文、卷次、篇章、概念定义 → Retrieval。
2. **Evidence gap 有条件优先**：只有当高代价判断确实被关键事实缺口阻塞时 → `diaocha-yanjiu` 或先检索资料；不要把“更多信息总是更好”当成触发条件。
3. **Framework 负责选方向**：从 7 个框架中最多选 1 个主框架。
4. **Atomic 负责执行**：默认选择最小充分集合，通常 1–4 个；允许 0 个。
5. **Composite 只在真正多阶段任务中触发**。

## 冲突消解

- `diaocha-yanjiu` vs `shishiqiushi-sigao`：前者采集缺失的一手信息，后者加工已经拥有但杂乱/冲突的信息。
- `shijian-renshilun` vs 普通学习：前者要求“行动—反馈—修正—再行动”闭环；教程或资源推荐本身不触发。
- `maodun-fenxi` vs 单点问题：前者用于多个问题/力量之间找主要矛盾或瓶颈；单一已知 bug 不触发。
- `maodun-fenxi` vs `maodun-techuxing`：前者回答“当前主要问题是什么”，后者回答“这套方法在当前条件下是否适用”。机械照搬标杆、模板，或旧方法在新环境失效，优先 `maodun-techuxing`。
- `jianmiezhan-jizhong-bingli` vs `bianzheng-pingheng`：前者强调关键局部聚焦，后者强调多目标动态平衡；先看任务是否存在一个明确瓶颈。
- `qunzhong-luxian` vs `yiban-gebie-zhidao`：前者持续收集-提炼-验证，后者偏向试点与推广。

## 最小选择原则

- 不因为 Skill “也能解释”就选择它；必须对当前任务有不可忽略的增益。
- 能直接回答 → `direct`。
- 能用 1 个 Atomic → 不选 3 个。
- 不使用“邻近 Skill 全选”的保险策略。
- `source_lookup` 默认 `atomic_skills=[]`。

## 输出标签建议

为减少原文与迁移混淆，可在分析内部使用：

- `[SOURCE]` 本地 corpus 可核验事实；
- `[INTERPRETATION]` 对原文方法的解释；
- `[TRANSFER]` 迁移到现代场景；
- `[ASSUMPTION]` 用户场景中的待验证假设。

最终回答无需机械显示全部标签，但必须保持这四类内容不混淆。
