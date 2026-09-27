# Evaluation

本目录把验收拆成三层：静态完整性、证据忠实度、模型路由效果。

## CI 自动执行

- 25 个 Atomic Skill / 7 个 Framework / 4 个 Composite Skill 的结构完整性。
- 25 个上游 `test-prompts.json` 的 schema 与正反例完整性。
- corpus 索引、Source manifest、Skill -> Source evidence map。
- 本地存在来源的 R 段引文必须 100% 可对齐；外部缺失来源必须进入显式 allowlist。
- Retrieval smoke test。

GitHub Actions 会上传：

- `evidence-audit`：corpus manifest、证据映射、证据覆盖率。
- `skill-test-audit`：25 个 Skill 共 150 条上游 routing cases 的规范化 benchmark。

## 运行 Router Benchmark

先初始化上游并生成 Atomic benchmark：

```bash
python3 scripts/sync_upstreams.py
python3 eval/build_atomic_benchmark.py
```

配置任意 OpenAI-compatible `/chat/completions` endpoint：

```bash
export MAOXUAN_BENCH_BASE_URL='https://your-endpoint.example/v1'
export MAOXUAN_BENCH_API_KEY='...'
export MAOXUAN_BENCH_MODEL='your-model'
python3 eval/run_router_benchmark.py --workers 4
```

不联网只检查 harness：

```bash
python3 eval/run_router_benchmark.py --dry-run
```

统一数据集包含：

- 150 条 Atomic cases：75 should-trigger、50 should-not-trigger、25 edge cases；
- 6 条系统级 Router cases：source lookup / method application / composite task。

自动评分规则：

- `should_trigger`：目标 Atomic Skill 必须被选中；
- `should_not_trigger`：目标 Skill 不得被选中；
- `edge_case`：保留输出供人工/LLM judge 复核，不自动计分；
- 系统 Router case：route 必须正确，并检查要求的 framework / atomic / composite / retrieval component。

输出保存在 `eval/results/`，包括逐 case JSONL 和 summary JSON。

## 尚未自动化的 Task Gain

“用了 Skill 后答案是否比 Vanilla LLM 更好”需要面向具体任务的 judge rubric，不能用 Router 命中率替代。后续应比较：

`Vanilla LLM` vs `RAG only` vs `Atomic Skills` vs `Framework + Atomic` vs `Full Router + Retrieval + Composite`。
