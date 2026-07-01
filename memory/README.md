# markdown 记忆文档目录

本目录与 Neo4j 知识图谱（`rabbitbot-memory` 容器内的 Graphiti/`agent_memory.py`）共同构成
RabbitBot 的记忆检索来源。二者由 `rabbitbot/memory/agent_memory.py::AgentMemory.query_combined`
合并检索：

- Neo4j 检索异常（连接失败等）或查询结果为空时，会被自动忽略，仅使用本目录下的 markdown 结果。
- 本目录下的文档只用于检索（只读），不会被程序写入；新增/修改/删除记忆条目仍通过
  `/update` 接口写入 Neo4j。

## 文档格式约定

- 直接放置 `.md` 文件（支持子目录，递归扫描）。
- 按标题（`#`~`######`）切分为独立可检索片段；同一标题下正文如果过长，会再按空行分段。
- 没有任何标题的文件，整篇正文作为一个片段。
- 检索时使用与 Neo4j 相同的 embedding 服务（`GRAPHITI_EMBD_MODEL` / `GRAPHITI_EMBD_MODEL_URL`）
  计算片段与查询的余弦相似度，取全局最高分（含 Neo4j 候选）作为最终匹配。

## 生效方式

- `rabbitbot-memory` 容器通过 bind mount 将本目录（宿主机 `/mnt/disk1/gt/air_robot_gt_projects/memory`）
  映射为容器内 `/workspace/projects/memory`，运行期直接可见。
- 文档内容变更后无需重启服务：`MarkdownMemoryStore` 按文件 mtime 增量刷新，下次检索请求会自动感知新增/修改/删除的文件。
- 可通过环境变量 `RABBITBOT_MEMORY_DOCS_DIR` 覆盖默认目录（默认即本目录）。
- 可调用 `GET http://127.0.0.1:28182/memory_status` 查看当前文档数、分片数与 Neo4j 连通性，用于排查“为什么没检索到”。
