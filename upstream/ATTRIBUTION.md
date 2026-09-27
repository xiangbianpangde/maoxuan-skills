# Upstream Attribution

## kangarooking/mao-selected-works-skill

- 用途：25 个 Atomic Skills 与各自测试。
- 锁定版本：`5058fe41ad7acd8e04cc53de96a57a91938b67d1`
- 许可证：MIT（副本见 `licenses/kangarooking-MIT.txt`）。
- 本项目通过 `scripts/sync_upstreams.py` 下载到 `vendor/kangarooking/`，并在其上增加 Router、Evidence、Composite 与 Eval，不修改上游作者归属。

## leezythu/maoxuan-skill

- 用途：7 个核心心智模型、高层总体分析入口及研究参考。
- 锁定版本：`4376a65020b1fd96af65052ccd30accaddedc3f1`
- 许可证：MIT（副本见 `licenses/leezythu-MIT.txt`）。
- 本项目默认不采用“第一人称角色扮演”为运行方式，而是把 7 个模型规范化成 Planner/Framework 层。

## henryczq/mao-selected-works-skill

- 用途：检索层架构参考（本地 corpus、keyword/hybrid、embedding、reranker）。
- 锁定参考版本：`98eb026e760e2daa71740c30b56f0c6a9ff950d0`
- 审计时仓库根目录未见明确 LICENSE，因此本项目**不复制其代码或全文语料**。`retrieval/` 为独立实现。

## 本仓库 `毛选md/`

它是本系统原文检索的唯一事实源。文本本身的版权、版本与再分发许可不由上述 MIT License 覆盖，仓库维护者应单独核验其来源与使用条件。
