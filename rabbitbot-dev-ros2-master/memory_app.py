
import os
import time
from typing import Dict, Any
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from rabbitbot.memory.agent_memory import AgentMemory
from rabbitbot.provider import get_llm
from rabbitbot.tools.logging import logger
import ast
import tempfile
from typing import List
from graphiti_core.nodes import EntityNode
from neo4j import GraphDatabase

app = FastAPI()

llm_cfg = get_llm(None, None)
neo4j_url = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
neo4j_password = os.getenv('NEO4J_PASSWORD', 'your_password')
embd_model = os.getenv('GRAPHITI_EMBD_MODEL', 'Qwen3-Embedding-0.6B')
embd_model_url = os.getenv('GRAPHITI_EMBD_MODEL_URL', 'http://localhost:8005/v1')
rerank_model = os.getenv('GRAPHITI_RERANK_MODEL', llm_cfg['model'])
rerank_model_url = os.getenv('GRAPHITI_RERANK_MODEL_URL', 'http://localhost:8000/v1')

print(embd_model)
print(embd_model_url)
print(rerank_model)
print(rerank_model_url)

agent = AgentMemory(
    llm_cfg=llm_cfg,
    neo4j_url=neo4j_url,
    neo4j_user=neo4j_user,
    neo4j_password=neo4j_password,
    embd_model=embd_model,
    embd_model_url=embd_model_url,
    rerank_model=rerank_model,
    rerank_model_url=rerank_model_url,
)


def sanitize_for_json(value: Any) -> Any:
    """Convert Neo4j/Graphiti values to FastAPI JSON-serializable values."""
    if isinstance(value, dict):
        return {key: sanitize_for_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_for_json(item) for item in value]
    if hasattr(value, "iso_format"):
        return value.iso_format()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def parse_literal_if_possible(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return value


def node_to_response_dict(node: EntityNode) -> Dict[str, Any]:
    attributes: Dict[str, Any] = sanitize_for_json(dict(node.attributes or {}))
    for key in ("location", "pose"):
        if key in attributes:
            attributes[key] = sanitize_for_json(parse_literal_if_possible(attributes[key]))

    return {
        "uuid": node.uuid,
        "name": node.name,
        "group_id": node.group_id,
        "summary": node.summary,
        "attributes": attributes,
    }


def create_empty_node_response(task: str) -> Dict[str, Any]:
    return {
        "uuid": "114514",
        "name": "异常结点",
        "group_id": "",
        "summary": "不好意思，我检索不到您想要找的物品",
        "attributes": {
            "location": None,
            "image_path": None,
            "description": "不好意思，我检索不到您想要找的物品",
        },
    }

@app.post("/update")
async def update_api(task: str = Form(...)):
    try:
        print(f"Get data")
        print(task)
        entities = ast.literal_eval(task)
        print(entities)
        await agent.init_graphiti_if_not()
        await agent.update(entities)

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.post("/get_all_names")
async def get_all_nodes_name(task: str = Form(...)):
    try:
        driver = GraphDatabase.driver(neo4j_url, auth=(neo4j_user, neo4j_password))
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN n")
            nodes = []
            for record in result:
                nodes.append(record["n"])
        node_name=[]
        for node in nodes:
            if node.get("name")!="房间":
               node_name.append(node.get("name"))
        print(node_name)
        driver.close()
        return node_name
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/get_group_names")
async def get_group_nodes_name(task: str = Form(...)):
    try:
        driver = GraphDatabase.driver(neo4j_url, auth=(neo4j_user, neo4j_password))
        with driver.session() as session:
            result = session.run(f"MATCH (n) WHERE n.group_id='{task}' RETURN n")
            nodes = []
            for record in result:
                nodes.append(record["n"])
        node_name=[]
        for node in nodes:
            if node.get("name")!="房间":
               node_name.append(node.get("name"))
        print(node_name)
        driver.close()
        return node_name
    except Exception as e:
        print(str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/get_group_summary")
async def get_group_nodes_name(task: str = Form(...)):
    try:
        driver = GraphDatabase.driver(neo4j_url, auth=(neo4j_user, neo4j_password))
        with driver.session() as session:
            result = session.run(f"MATCH (n) WHERE n.group_id='{task}' RETURN n")
            nodes = []
            for record in result:
                nodes.append(record["n"])

        # 创建字典存储 name:summary 映射
        node_dict = {}
        for node in nodes:
            name = node.get("name")
            if name and name != "房间":
                node_dict[name] = node.get("summary", "")

        print(node_dict)
        driver.close()
        return node_dict

    except Exception as e:
        print(str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/query")
async def query_api(task: str = Form(...)):
    """记忆语义检索：合并 Neo4j 知识图谱与项目根目录 memory/ 下的 markdown 文档两个来源，
    按余弦相似度取全局最佳匹配返回；Neo4j 检索异常或为空时自动忽略该来源，仅用 markdown 结果。
    """
    try:
        await agent.init_graphiti_if_not()
        task_data = ast.literal_eval(task)
        if not isinstance(task_data, dict):
            return JSONResponse(content={"error": "task must be a dict"}, status_code=400)
        query, group_name = task_data['query'], task_data['group_name']
        logger.info(f"/query 请求: query_len={len(query)}, group_name={group_name}")
        if query == "异常结点":
            return create_empty_node_response(query)

        start = time.monotonic()
        task_embedding = await agent.create_embedding(query)
        graph_nodes, markdown_scored_nodes = await agent.query_combined(query, group_name=group_name, limit=5)

        similarity_threshold = 0.35
        best_similarity = 0
        best_match = None
        best_source = None

        for node in graph_nodes:
            # 为节点名称生成 embedding，计算相似度（沿用既有 Neo4j 打分方式）
            node_embedding = await agent.create_embedding(node.name)
            similarity = agent.cosine_similarity(task_embedding, node_embedding)
            logger.debug(f"neo4j 候选: name={node.name}, 相似度={similarity:.4f}")
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = node
                best_source = "neo4j"

        for similarity, node in markdown_scored_nodes:
            # markdown 分片相似度已基于全文 embedding 计算，直接复用，无需再对 name 重新计算
            logger.debug(
                f"markdown 候选: name={node.name}, doc={node.attributes.get('doc_path')}, 相似度={similarity:.4f}"
            )
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = node
                best_source = "markdown"

        elapsed = time.monotonic() - start
        if best_similarity < similarity_threshold or best_match is None:
            logger.info(
                f"/query 未命中(低于阈值 {similarity_threshold}): group_name={group_name}, "
                f"最高相似度={best_similarity:.4f}, neo4j候选={len(graph_nodes)}, "
                f"markdown候选={len(markdown_scored_nodes)}, 耗时={elapsed:.3f}s"
            )
            return create_empty_node_response(query)

        logger.info(
            f"/query 命中: source={best_source}, name={best_match.name}, 相似度={best_similarity:.4f}, "
            f"neo4j候选={len(graph_nodes)}, markdown候选={len(markdown_scored_nodes)}, 耗时={elapsed:.3f}s"
        )
        return node_to_response_dict(best_match)

    except Exception as e:
        logger.error(f"/query 请求处理失败: error={e}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/memory_status")
async def memory_status():
    """诊断端点：查看 markdown 记忆源当前扫描到的文档/分片数量，以及 Neo4j 连通性。"""
    try:
        await agent.markdown_store.refresh()
        markdown_doc_count = len({chunk.doc_path for chunk in agent.markdown_store._chunks})
        markdown_chunk_count = len(agent.markdown_store._chunks)
    except Exception as exc:
        logger.error(f"/memory_status 读取 markdown 记忆状态失败: error={exc}", exc_info=True)
        markdown_doc_count = 0
        markdown_chunk_count = 0

    neo4j_reachable = True
    neo4j_error = None
    try:
        driver = GraphDatabase.driver(neo4j_url, auth=(neo4j_user, neo4j_password))
        with driver.session() as session:
            session.run("RETURN 1")
        driver.close()
    except Exception as exc:
        neo4j_reachable = False
        neo4j_error = str(exc)
        logger.warning(f"/memory_status 检测到 Neo4j 不可达: error={exc}")

    return {
        "markdown_docs_dir": str(agent.markdown_store.docs_dir),
        "markdown_doc_count": markdown_doc_count,
        "markdown_chunk_count": markdown_chunk_count,
        "neo4j_reachable": neo4j_reachable,
        "neo4j_error": neo4j_error,
    }
