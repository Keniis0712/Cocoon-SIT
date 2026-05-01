"""cache memory keywords

Revision ID: 0028_mem_kw_cache
Revises: 0027_mem_profiles_and_ops
Create Date: 2026-05-01 20:50:00
"""

from __future__ import annotations

import json
import re

import jieba.analyse
from alembic import op
import sqlalchemy as sa

from app.models.identity import new_id


revision: str = "0028_mem_kw_cache"
down_revision: str | None = "0027_mem_profiles_and_ops"
branch_labels = None
depends_on = None


_OPAQUE_TAG_RE = re.compile(
    r"^(?:"
    r"[0-9a-fA-F]{32}"
    r"|"
    r"[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}"
    r")$"
)
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_ASCII_WORD_RE = re.compile(r"^[a-z0-9][a-z0-9_./+-]*$")
_STOPWORDS = {
    "active",
    "agent",
    "ai",
    "archived",
    "assistant",
    "candidate",
    "chat",
    "content",
    "conversation",
    "current",
    "default",
    "memory",
    "meta",
    "project",
    "reply",
    "runtime",
    "session",
    "summary",
    "system",
    "task",
    "user",
    "上下文",
    "内容",
    "信息",
    "任务",
    "偏好",
    "关系",
    "分析",
    "对话",
    "当前",
    "总结",
    "摘要",
    "系统",
    "聊天",
    "规则",
    "记忆",
    "设定",
    "说明",
    "项目",
    "用户",
}


def _normalize_keyword(raw_keyword: str) -> str | None:
    keyword = str(raw_keyword or "").strip()
    if not keyword:
        return None
    normalized = keyword.lower()
    if normalized in _STOPWORDS or normalized.isdigit():
        return None
    if _OPAQUE_TAG_RE.fullmatch(keyword):
        return None
    if _CJK_RE.search(keyword):
        return keyword if len(keyword) >= 2 else None
    if not _ASCII_WORD_RE.fullmatch(normalized):
        return None
    return normalized if len(normalized) >= 3 else None


def _build_keyword_cache(summary: str | None, content: str | None) -> list[dict[str, float | str]]:
    source_text = "\n".join(part.strip() for part in (summary or "", content or "") if part and part.strip())
    if not source_text:
        return []
    weights: dict[str, float] = {}
    for keyword, weight in jieba.analyse.extract_tags(source_text, topK=24, withWeight=True):
        normalized = _normalize_keyword(keyword)
        if not normalized:
            continue
        weights[normalized] = max(weights.get(normalized, 0.0), float(weight))
    return [
        {"word": word, "weight": round(weight, 4)}
        for word, weight in sorted(weights.items(), key=lambda item: (-item[1], item[0]))[:8]
    ]


def upgrade() -> None:
    with op.batch_alter_table("memory_embeddings") as batch_op:
        batch_op.alter_column("embedding_provider_id", existing_type=sa.String(length=64), nullable=True)
        batch_op.alter_column("model_name", existing_type=sa.String(length=128), nullable=True)
        batch_op.alter_column("dimensions", existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column("keywords_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))

    connection = op.get_bind()
    memories = connection.execute(
        sa.text(
            """
            SELECT id, summary, content
            FROM memory_chunks
            ORDER BY created_at ASC
            """
        )
    ).mappings().all()
    existing_embedding_ids = {
        row["memory_chunk_id"]: row["id"]
        for row in connection.execute(
            sa.text("SELECT id, memory_chunk_id FROM memory_embeddings")
        ).mappings().all()
    }

    for memory in memories:
        keywords_json = _build_keyword_cache(memory.get("summary"), memory.get("content"))
        existing_id = existing_embedding_ids.get(memory["id"])
        if existing_id:
            connection.execute(
                sa.text(
                    "UPDATE memory_embeddings SET keywords_json = :keywords_json WHERE id = :id"
                ),
                {"id": existing_id, "keywords_json": json.dumps(keywords_json, ensure_ascii=False)},
            )
            continue
        connection.execute(
            sa.text(
                """
                INSERT INTO memory_embeddings (
                    id,
                    memory_chunk_id,
                    embedding_provider_id,
                    model_name,
                    dimensions,
                    embedding,
                    keywords_json,
                    usage_json,
                    meta_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :memory_chunk_id,
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    :keywords_json,
                    :usage_json,
                    :meta_json,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "id": new_id(),
                "memory_chunk_id": memory["id"],
                "keywords_json": json.dumps(keywords_json, ensure_ascii=False),
                "usage_json": json.dumps({}, ensure_ascii=False),
                "meta_json": json.dumps({}, ensure_ascii=False),
            },
        )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            DELETE FROM memory_embeddings
            WHERE embedding_provider_id IS NULL
              AND model_name IS NULL
              AND dimensions IS NULL
              AND embedding IS NULL
            """
        )
    )

    with op.batch_alter_table("memory_embeddings") as batch_op:
        batch_op.drop_column("keywords_json")
        batch_op.alter_column("dimensions", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("model_name", existing_type=sa.String(length=128), nullable=False)
        batch_op.alter_column("embedding_provider_id", existing_type=sa.String(length=64), nullable=False)
