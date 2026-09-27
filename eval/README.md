# Evaluation

本项目不把“有 25 个 Skill”当作完成标准。建议至少测五个维度：

1. **Routing Accuracy**：是否选择正确的 Retrieval / Framework / Atomic / Composite。
2. **Source Fidelity**：声称来自原文的内容能否在本地 corpus 找到。
3. **Boundary Accuracy**：不适用时是否拒绝套方法。
4. **Composition Accuracy**：多个 Atomic Skill 的顺序是否合理，是否存在不必要调用。
5. **Task Gain**：与 Vanilla LLM、RAG-only、Atomic-only、Framework-only 相比，整合系统是否提高任务质量。

推荐对照组：

```text
A Vanilla Model
B Model + Retrieval
C Model + 25 Atomic Skills
D Model + 7 Frameworks
E Model + Retrieval + Framework Router + Atomic + Composite + Evidence
```
