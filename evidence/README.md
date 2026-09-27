# Evidence layer

本目录把方法论 Skill 与本仓库 `毛选md/` 原文建立可审计关系。

## 生成文件

- `corpus-manifest.generated.json`：本地 corpus 文件、卷次、文章号与哈希。
- `skill-source-map.generated.json`：Atomic Skill 的篇章来源和 R 段引文到 Source ID 的映射。
- `../eval/evidence-coverage.generated.json`：覆盖率与对齐类型统计。

这些 generated 文件由 CI 生成并作为 `evidence-audit` artifact 上传，不作为手工事实源维护。

## 引文对齐类型

- `exact`：连续文本精确对齐。
- `ellipsis`：上游引文显式使用省略号，多个片段在同一来源中按顺序存在。
- `composite`：上游 blockquote 把同一篇来源中不连续的多段原文拼接在一起；证据映射保留多个非连续 Source ID，不把它伪装成连续引文。
- `fuzzy`：仅用于版本字词、标点、脚注等差异，最低分数门槛为 0.90。

## 外部来源例外

`external-source-allowlist.json` 是严格例外清单。如果上游 Skill 声明的来源不在当前 `毛选md/` corpus 中，只有明确列入该文件才允许 CI 通过。新增缺失来源默认视为错误，防止标题拼写错误或模糊匹配被静默接受。

该 allowlist 只表达“当前本地 corpus 没有这篇材料”，不代表对上游引用的历史真实性作独立认证。
