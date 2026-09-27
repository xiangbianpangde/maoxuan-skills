# Framework Layer

这一层不是新的“第 26–32 个 Skill”，而是 Planner。

高层框架来自 `leezythu/maoxuan-skill` 的 7 个核心模型；本仓库把它们规范化为对 25 个 Atomic Skills 的路由关系。完整上游 Skill 和研究参考可以用 `scripts/sync_upstreams.py` 同步到 `vendor/leezythu/`。

规则：

1. 高层框架负责确定分析方向，不负责替代原子 Skill 的执行步骤。
2. 每次复杂任务优先选 1 个主框架；必要时加 1 个辅助框架。
3. 迁移到现代场景时明确标记为“方法迁移”，不要声称现代业务案例来自原文。
4. “角色扮演/第一人称毛泽东”不是本项目默认模式；默认使用可审计的分析表达。
