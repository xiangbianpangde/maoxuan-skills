# Evidence Layer

目标：让“方法论解释”可以追溯到本仓库自己的 `毛选md/`，而不是只相信上游 Skill 中的引用。

生成顺序：

```bash
python3 scripts/sync_upstreams.py
python3 scripts/build_source_manifest.py
python3 retrieval/build_index.py
python3 scripts/build_evidence_map.py
```

输出：

- `corpus-manifest.generated.json`：文章文件 SHA256、卷次、标题；
- `skill-source-map.generated.json`：上游 Skill 声明的来源篇目 + R 段引文在本地 corpus 中的匹配结果；
- SQLite 中每个段落都有稳定 `MX-Vxx-Axxx-Pxxxx` Source ID。

匹配失败不是“没有证据”，而是需要人工核验：版本、标点、节选方式都可能造成精确匹配失败。
