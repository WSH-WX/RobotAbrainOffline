
from graphiti_core import Graphiti
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.nodes import EntityNode
from graphiti_core.edges import EntityEdge
from graphiti_core.search.search_config_recipes import NODE_HYBRID_SEARCH_RRF

import os
import uuid
import asyncio
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple

from rabbitbot.tools.logging import logger
from rabbitbot.memory.markdown_memory import MarkdownMemoryStore

# markdown 记忆文档目录默认在项目根目录（air_robot_gt_projects）下的 memory/ 子目录，
# 与 provider.py::_load_combined_data 对 combined_data.json 的路径约定一致
# （Path(__file__).resolve() 从 rabbitbot/memory/agent_memory.py 向上数 3 层即项目根目录）。
_DEFAULT_MARKDOWN_DOCS_DIR = Path(__file__).resolve().parents[3] / "memory"


class AgentMemory:
    """
    AgentMemory is a singleton class that manages the memory of an agent, allowing it to store and retrieve information
    about its interactions and knowledge.
    """
    # _instance = None

    # def __new__(cls, *args, **kwargs):
    #     if cls._instance is None:
    #         cls._instance = super(AgentMemory, cls).__new__(cls)
    #     return cls._instance

    def __init__(
        self,
        llm_cfg: dict,
        neo4j_url: str,
        neo4j_user: str,
        neo4j_password: str,
        embd_model: str,
        embd_model_url: str,
        rerank_model: str,
        rerank_model_url: str,
        markdown_docs_dir: str = None,
    ):
        # if hasattr(self, 'graphiti'):
        #     return

        self.neo4j_url = neo4j_url
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.embd_model = embd_model
        self.embd_model_url = embd_model_url
        self.rerank_model = rerank_model
        self.rerank_model_url = rerank_model_url
        self.llm_cfg = LLMConfig(
            api_key=llm_cfg['api_key'],
            model=llm_cfg['model'],
            small_model=llm_cfg['model'],
            base_url=llm_cfg['model_server'],
        )
        self.graphiti = Graphiti(
            self.neo4j_url,
            self.neo4j_user,
            self.neo4j_password,
            llm_client=OpenAIClient(config=self.llm_cfg),
            embedder=OpenAIEmbedder(  # at jrf
                config=OpenAIEmbedderConfig(
                    api_key=llm_cfg['api_key'],
                    embedding_model=self.embd_model,
                    base_url=self.embd_model_url,
                )
            ),
            cross_encoder=OpenAIRerankerClient( # at jrf
                config=LLMConfig(
                    api_key=llm_cfg['api_key'],
                    model=self.rerank_model,
                    base_url=self.rerank_model_url,
                )
            )
        )
        self.initialized = False

        docs_dir = markdown_docs_dir or os.getenv('RABBITBOT_MEMORY_DOCS_DIR') or _DEFAULT_MARKDOWN_DOCS_DIR
        self.markdown_store = MarkdownMemoryStore(
            docs_dir=docs_dir,
            embed_fn=self.create_embedding,
            cosine_fn=self.cosine_similarity,
        )
        logger.info(f"AgentMemory 初始化完成: neo4j_url={self.neo4j_url}, markdown_docs_dir={docs_dir}")

    async def create_embedding(self, text: str) -> List[float]:
        if not self.initialized:
            await self.init_graphiti_if_not()
        clean_text = text.replace('\n', ' ').strip()
        embedding = await self.graphiti.embedder.create(input_data=[clean_text])
        return embedding

    def create_embedding_sync(self, text: str) -> List[float]:
        loop = self.get_event_loop()
        return loop.run_until_complete(self.create_embedding(text))

    def cosine_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """计算两个embedding的余弦相似度"""
        a = np.array(embedding1)
        b = np.array(embedding2)

        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0

        return float(dot_product / (norm_a * norm_b))

    def get_all_nodes_name(self):
        driver = GraphDatabase.driver(self.neo4j_url, auth=(self.neo4j_user, self.neo4j_password))
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN n")
            nodes = []
            for record in result:
                nodes.append(record["n"])
        node_name=[]
        for node in nodes:
            node_name.append(node.get("name"))
        print(node_name)
        driver.close()

    def update_sync(self, entities: dict):
        asyncio.get_event_loop().run_until_complete(self.update(entities))

    async def update(self, entities: dict):
        graphiti = self.graphiti
        room_uuid = "efe754d7-cb90-430c-9143-5c51baa6755"
        #group_uuid = str(uuid.uuid4())

        # 1. 房间节点 —— 用 uuid 当主键，保证全局唯一
        room_node = EntityNode(
            uuid=room_uuid,
            name="房间",
            group_id="",
            summary="房间节点",
            attributes={},
            primary_key="uuid",
            entity_type="Room"
        )

        # 2. 依次处理每个实体
        for entity_name, (summary, description, location) in entities.items():
            entity_uuid = str(uuid.uuid4())
            group_uuid = str(uuid.uuid4())
            print(f"定义 Entity: {entity_name} -> {entity_uuid}")
            #input("Press ENTER to add new entity")

            entity_node = EntityNode(
                uuid=entity_uuid,
                name=entity_name,
                group_id=group_uuid,
                summary=summary,
                attributes={
                    "location": location,
                    "image_path": None,
                    "description": description,
                },
                primary_key="uuid",
                entity_type="Object"
            )

            edge = EntityEdge(
                group_id="",
                source_node_uuid=entity_uuid,
                target_node_uuid=room_uuid,
                created_at=datetime.now(),
                name="属于",
                fact=f"{entity_name}属于房间"
            )

            # 3. 写入图库（节点按 uuid 做 MERGE，不会互盖）
            await graphiti.add_triplet(entity_node, edge, room_node)

    def update_sync_special(self, entities: dict):
        asyncio.get_event_loop().run_until_complete(self.update_special(entities))

    async def update_special(self, entities: dict):
        if self.initialized:
            return
        await self.graphiti.build_indices_and_constraints()
        self.initialized = True
        graphiti = self.graphiti
        room_uuid = "efe754d7-cb90-430c-9143-5c51baa6755"
        room_node = EntityNode(
            uuid=room_uuid,
            name="房间",
            group_id="",
            attributes={}
        )
        print(f"room_uuid:{room_uuid}")
        for entity_name, (summary, describtion, location) in entities.items():
            # 定义 Entity
            print(f"定义 Entity: {entity_name}")
            entity_uuid = str(uuid.uuid4())
            print(f"UUID: {entity_uuid}")
            entity_node = EntityNode(
                uuid=entity_uuid,
                name=entity_name,
                group_id="",
                summary=summary,
                attributes={
                    'location': location,
                    'describtion': describtion,
                },
            )
            # 定义边
            edge = EntityEdge(
                group_id="",
                source_node_uuid=entity_uuid,    # 以实体为source
                target_node_uuid=room_uuid,      # 房间为target
                created_at=datetime.now(),
                name="属于",                      # 关系名
                fact=f"{entity_name}属于房间"      # 事实描述
            )
            await graphiti.add_triplet(entity_node, edge, room_node)

    def get_event_loop(self):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError as e:
            if 'There is no current event loop in thread' in str(e):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            else:
                raise e
        return loop

    def query_sync(self, query: str, limit: int = 3):
        loop = self.get_event_loop()
        return loop.run_until_complete(self.query(query, limit))

    async def query(self, query: str, group_name:str, limit: int = 2):
        node_search_config = NODE_HYBRID_SEARCH_RRF.model_copy(deep=True)
        node_search_config.limit = limit
        print(f"query: {query}")
        graphiti = self.graphiti
        print(graphiti)
        # 暂时不使用 group_ids 过滤，避免 Neo4j 约束验证中文报错
        # 如果需要按分组查询，先检查 group_name 是否符合约束要求
        import re
        if re.match(r'^[a-zA-Z0-9_-]+$', group_name):
            node_search_results = await graphiti._search(
                query=f'{query}',
                config=node_search_config,
                group_ids=[f"{group_name}"]
            )
        else:
            # 中文 group_name 时跳过 group_ids 过滤
            print(f"Skipping group_ids filter for non-alphanumeric group_name: {group_name}")
            node_search_results = await graphiti._search(
                query=f'{query}',
                config=node_search_config,
                group_ids=[]
            )
        print(f"node_search_results: {node_search_results}")
        return node_search_results.nodes

    def _chunk_to_entity_node(self, chunk) -> EntityNode:
        """把 markdown 分片包装成与 Neo4j 检索结果同构的 EntityNode，供下游统一消费。"""
        return EntityNode(
            uuid=chunk.chunk_id,
            name=chunk.title,
            group_id="markdown",
            summary=chunk.text[:200],
            attributes={
                'location': None,
                'image_path': None,
                'description': chunk.text,
                'source': 'markdown',
                'doc_path': chunk.doc_path,
            },
        )

    async def query_combined(
        self, query: str, group_name: str, limit: int = 5
    ) -> Tuple[List[EntityNode], List[Tuple[float, EntityNode]]]:
        """合并 Neo4j 知识图谱与 markdown 文档两个记忆来源的检索结果。

        Neo4j 检索异常（连接失败、约束报错等）或返回为空时，忽略该来源、仅记录日志，
        不影响 markdown 检索结果的返回；两个来源均可能为空，由调用方按相似度阈值判定是否命中。
        返回 (graph_nodes, markdown_scored_nodes)：graph_nodes 未预先打分（沿用既有调用方的打分方式），
        markdown_scored_nodes 为 (相似度, EntityNode) 列表（相似度已基于分片全文计算，无需再对 name 重新计算）。
        """
        graph_nodes: List[EntityNode] = []
        try:
            graph_nodes = await self.query(query, group_name=group_name, limit=limit)
        except Exception as exc:
            logger.warning(
                f"Neo4j 记忆检索异常，本次查询忽略该来源: group_name={group_name}, "
                f"query_len={len(query)}, error={exc}"
            )
        if not graph_nodes:
            logger.debug(f"Neo4j 记忆检索为空，本次查询仅使用 markdown 来源: group_name={group_name}")

        markdown_scored: List[Tuple[float, EntityNode]] = []
        try:
            markdown_hits = await self.markdown_store.search(query, limit=limit)
            markdown_scored = [(score, self._chunk_to_entity_node(chunk)) for score, chunk in markdown_hits]
        except Exception as exc:
            logger.error(f"markdown 记忆检索异常，本次查询忽略该来源: query_len={len(query)}, error={exc}")

        return graph_nodes, markdown_scored

    async def close(self):
        await self.graphiti.close()

    async def init_graphiti_if_not(self):
        if self.initialized:
            return
        await self.graphiti.build_indices_and_constraints()
        self.initialized = True

    async def __aenter__(self):
        await self.graphiti.build_indices_and_constraints()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.close()

    def __enter__(self):
        self.get_event_loop().run_until_complete(self.graphiti.build_indices_and_constraints())
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.get_event_loop().run_until_complete(self.close())
