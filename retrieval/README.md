# Retrieval Layer

独立实现，吸收 `henryczq/mao-selected-works-skill` 的工程思路，但不复制其代码或语料。

能力：

- `catalog`：按卷列文章；
- `show`：按标题取整篇的段落化内容；
- `search`：标题/段落关键词检索，优先精确中文子串，FTS5 可用时作为补充；
- `hybrid`：关键词 + 可选远程 embedding + 可选 reranker；
- Stable Source ID：`MX-Vxx-Axxx-Pxxxx`。

数据库默认生成到 `index/maoxuan.sqlite3`，不提交版本库。
