# -*- coding: utf-8 -*-
import asyncio
import math
import os

from rabbitbot.memory.markdown_memory import MarkdownMemoryStore, split_markdown_into_chunks


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# 用关键词映射到正交向量的假 embedding，使相似度排序可预测，测试无需依赖真实 embedding 服务。
_KEYWORD_VECTORS = {
    "苹果": (1.0, 0.0, 0.0),
    "香蕉": (0.0, 1.0, 0.0),
    "导航": (0.0, 0.0, 1.0),
}


async def _fake_embed(text):
    vec = [0.0, 0.0, 0.0]
    for keyword, kw_vec in _KEYWORD_VECTORS.items():
        if keyword in text:
            vec = [a + b for a, b in zip(vec, kw_vec)]
    if vec == [0.0, 0.0, 0.0]:
        vec = [0.1, 0.1, 0.1]
    return vec


async def _flaky_embed(text):
    if "坏文档" in text:
        raise RuntimeError("模拟 embedding 服务失败")
    return await _fake_embed(text)


def test_split_markdown_into_chunks_by_heading():
    text = "# 标题一\n内容一\n\n## 标题二\n内容二第一段\n\n内容二第二段\n"
    chunks = split_markdown_into_chunks(text)
    assert [c[0] for c in chunks] == ["标题一", "标题二"]
    assert chunks[0][1] == "内容一"
    assert "内容二第一段" in chunks[1][1]
    assert "内容二第二段" in chunks[1][1]


def test_split_markdown_into_chunks_without_heading_keeps_whole_file():
    text = "没有标题的纯文本内容。\n第二行内容。"
    chunks = split_markdown_into_chunks(text)
    assert len(chunks) == 1
    assert chunks[0][0] is None
    assert "没有标题的纯文本内容" in chunks[0][1]


def test_split_markdown_into_chunks_long_section_splits_by_paragraph():
    long_paragraphs = "\n\n".join(f"第{i}段内容" * 50 for i in range(6))
    text = f"# 长标题\n{long_paragraphs}\n"
    chunks = split_markdown_into_chunks(text)
    assert len(chunks) > 1
    assert all(heading == "长标题" for heading, _ in chunks)


def test_refresh_missing_dir_returns_empty_without_raising(tmp_path):
    store = MarkdownMemoryStore(
        docs_dir=tmp_path / "does_not_exist",
        embed_fn=_fake_embed,
        cosine_fn=_cosine,
    )
    asyncio.run(store.refresh())
    assert store._chunks == []
    result = asyncio.run(store.search("苹果"))
    assert result == []


def test_search_ranks_by_similarity(tmp_path):
    (tmp_path / "fruit.md").write_text("# 水果\n苹果是一种水果。\n", encoding="utf-8")
    (tmp_path / "nav.md").write_text("# 展点\n机器人导航到展厅入口。\n", encoding="utf-8")

    store = MarkdownMemoryStore(docs_dir=tmp_path, embed_fn=_fake_embed, cosine_fn=_cosine)
    top = asyncio.run(store.search("苹果多少钱", limit=2))

    assert len(top) == 2
    best_score, best_chunk = top[0]
    assert best_chunk.doc_path == "fruit.md"
    assert best_score > top[1][0]


def test_refresh_picks_up_file_change_and_removal(tmp_path):
    doc_path = tmp_path / "doc.md"
    doc_path.write_text("# 原始标题\n苹果相关内容。\n", encoding="utf-8")

    store = MarkdownMemoryStore(docs_dir=tmp_path, embed_fn=_fake_embed, cosine_fn=_cosine)
    asyncio.run(store.refresh())
    assert len(store._chunks) == 1
    assert store._chunks[0].heading == "原始标题"

    # 显式往后调整 mtime，避免测试环境文件系统时间戳分辨率不足导致误判为“未变化”
    new_mtime = doc_path.stat().st_mtime + 5
    doc_path.write_text("# 修改后标题\n导航相关内容。\n", encoding="utf-8")
    os.utime(doc_path, (new_mtime, new_mtime))
    asyncio.run(store.refresh())
    assert len(store._chunks) == 1
    assert store._chunks[0].heading == "修改后标题"

    doc_path.unlink()
    asyncio.run(store.refresh())
    assert store._chunks == []


def test_refresh_skips_failed_chunk_without_raising(tmp_path):
    (tmp_path / "bad.md").write_text("# 坏文档\n这段内容会触发 embedding 失败。\n", encoding="utf-8")
    (tmp_path / "good.md").write_text("# 好文档\n苹果内容正常。\n", encoding="utf-8")

    store = MarkdownMemoryStore(docs_dir=tmp_path, embed_fn=_flaky_embed, cosine_fn=_cosine)
    asyncio.run(store.refresh())

    assert len(store._chunks) == 1
    assert store._chunks[0].doc_path == "good.md"


def test_chunk_title_falls_back_to_filename_stem(tmp_path):
    (tmp_path / "无标题文档.md").write_text("纯文本，没有任何标题。\n", encoding="utf-8")
    store = MarkdownMemoryStore(docs_dir=tmp_path, embed_fn=_fake_embed, cosine_fn=_cosine)
    asyncio.run(store.refresh())
    assert len(store._chunks) == 1
    assert store._chunks[0].title == "无标题文档"
