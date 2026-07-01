# -*- coding: utf-8 -*-
"""markdown 文档记忆源。

与 rabbitbot/memory/agent_memory.py 中的 Neo4j/Graphiti 知识图谱互补：
扫描项目根目录 memory/ 下的 markdown 文档，按标题切分为片段，复用现有 embedding
服务计算向量，提供基于余弦相似度的语义检索。目录缺失或为空时视为该来源不可用，
仅记录日志并返回空结果，不影响调用方（不抛异常、不中断 Neo4j 检索）。
"""

import hashlib
import re
import time
from pathlib import Path
from typing import Awaitable, Callable, List, Optional, Tuple

from rabbitbot.tools.logging import logger

# 单个标题下正文过长时，进一步按空行分段，避免单个 chunk 超出 embedding 输入上限。
_MAX_CHUNK_CHARS = 1200
_HEADING_RE = re.compile(r'^#{1,6}\s+(.*)$')


def split_markdown_into_chunks(text: str) -> List[Tuple[Optional[str], str]]:
    """按 markdown 标题切分正文，返回 (heading, content) 列表。

    没有任何标题时，整篇正文作为一个 heading=None 的分片；
    单个标题下正文超过 _MAX_CHUNK_CHARS 时按空行（段落）再次切分。
    """
    lines = text.splitlines()
    sections: List[Tuple[Optional[str], str]] = []
    current_heading: Optional[str] = None
    current_lines: List[str] = []

    for line in lines:
        match = _HEADING_RE.match(line)
        if match:
            joined = "\n".join(current_lines).strip()
            if joined:
                sections.append((current_heading, joined))
            current_heading = match.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)
    joined = "\n".join(current_lines).strip()
    if joined:
        sections.append((current_heading, joined))

    chunks: List[Tuple[Optional[str], str]] = []
    for heading, content in sections:
        if len(content) <= _MAX_CHUNK_CHARS:
            chunks.append((heading, content))
            continue
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        buf = ""
        for para in paragraphs:
            if buf and len(buf) + len(para) + 2 > _MAX_CHUNK_CHARS:
                chunks.append((heading, buf))
                buf = para
            else:
                buf = f"{buf}\n\n{para}" if buf else para
        if buf:
            chunks.append((heading, buf))
    return chunks


class MarkdownChunk:
    """一个可检索的 markdown 分片。"""

    def __init__(self, doc_path: str, heading: Optional[str], text: str,
                 embedding: List[float], mtime: float):
        self.doc_path = doc_path
        self.heading = heading
        self.text = text
        self.embedding = embedding
        self.mtime = mtime

    @property
    def title(self) -> str:
        if self.heading:
            return self.heading
        return Path(self.doc_path).stem

    @property
    def chunk_id(self) -> str:
        digest = hashlib.sha1(f"{self.doc_path}:{self.heading}".encode("utf-8")).hexdigest()[:12]
        return f"md:{digest}"


class MarkdownMemoryStore:
    """扫描 docs_dir 下的 markdown 文档并提供语义检索。

    embed_fn: 与 AgentMemory.create_embedding 同签名的异步函数 (text) -> List[float]。
    cosine_fn: 与 AgentMemory.cosine_similarity 同签名的同步函数 (vec, vec) -> float。
    """

    def __init__(
        self,
        docs_dir,
        embed_fn: Callable[[str], Awaitable[List[float]]],
        cosine_fn: Callable[[List[float], List[float]], float],
    ):
        self.docs_dir = Path(docs_dir)
        self._embed_fn = embed_fn
        self._cosine_fn = cosine_fn
        self._chunks: List[MarkdownChunk] = []
        self._file_mtimes = {}
        self._warned_missing_dir = False

    async def refresh(self):
        """增量刷新：仅重新计算新增/修改文件的 embedding，未变化文件直接复用缓存。"""
        start = time.monotonic()

        if not self.docs_dir.is_dir():
            if not self._warned_missing_dir:
                logger.warning(f"markdown 记忆目录不存在，该来源本次忽略: docs_dir={self.docs_dir}")
                self._warned_missing_dir = True
            self._chunks = []
            self._file_mtimes = {}
            return
        self._warned_missing_dir = False

        md_files = sorted(self.docs_dir.rglob("*.md"))
        found_paths = {str(p) for p in md_files}

        removed_paths = [p for p in self._file_mtimes if p not in found_paths]
        if removed_paths:
            removed_set = set(removed_paths)
            self._chunks = [c for c in self._chunks if str(self.docs_dir / c.doc_path) not in removed_set]
            for p in removed_paths:
                self._file_mtimes.pop(p, None)

        changed_files = 0
        new_chunk_count = 0
        failed_files = 0
        for path in md_files:
            path_str = str(path)
            try:
                mtime = path.stat().st_mtime
            except OSError as exc:
                logger.error(f"读取 markdown 文档状态失败，跳过该文件: path={path_str}, error={exc}")
                failed_files += 1
                continue
            if self._file_mtimes.get(path_str) == mtime:
                continue

            changed_files += 1
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                logger.error(f"读取 markdown 文档内容失败，跳过该文件: path={path_str}, error={exc}")
                failed_files += 1
                continue

            rel_path = str(path.relative_to(self.docs_dir))
            self._chunks = [c for c in self._chunks if c.doc_path != rel_path]

            for heading, content in split_markdown_into_chunks(text):
                embed_input = f"{heading}\n{content}" if heading else content
                try:
                    embedding = await self._embed_fn(embed_input)
                except Exception as exc:
                    logger.error(
                        f"markdown 分片 embedding 计算失败，跳过该分片: doc={rel_path}, "
                        f"heading={heading}, error={exc}"
                    )
                    continue
                self._chunks.append(MarkdownChunk(
                    doc_path=rel_path, heading=heading, text=content,
                    embedding=embedding, mtime=mtime,
                ))
                new_chunk_count += 1
            self._file_mtimes[path_str] = mtime

        elapsed = time.monotonic() - start
        if changed_files or removed_paths or failed_files:
            logger.info(
                f"markdown 记忆刷新完成: docs_dir={self.docs_dir}, 文档总数={len(md_files)}, "
                f"变更文档={changed_files}, 删除文档={len(removed_paths)}, 失败文档={failed_files}, "
                f"新增分片={new_chunk_count}, 当前总分片={len(self._chunks)}, 耗时={elapsed:.3f}s"
            )
        else:
            logger.debug(
                f"markdown 记忆无变化: 文档总数={len(md_files)}, 当前总分片={len(self._chunks)}, "
                f"耗时={elapsed:.3f}s"
            )

    async def search(self, query: str, limit: int = 5) -> List[Tuple[float, MarkdownChunk]]:
        """按查询文本的语义相似度返回 top-N 分片，附带相似度分数。"""
        await self.refresh()
        if not self._chunks:
            logger.debug("markdown 记忆当前无可用分片，跳过检索")
            return []

        query_embedding = await self._embed_fn(query)
        scored = [(self._cosine_fn(query_embedding, chunk.embedding), chunk) for chunk in self._chunks]
        scored.sort(key=lambda item: item[0], reverse=True)
        top = scored[:limit]

        if top:
            logger.debug(
                f"markdown 记忆检索: query_len={len(query)}, 候选分片={len(scored)}, "
                f"返回={len(top)}, 最高相似度={top[0][0]:.4f}"
            )
        return top
