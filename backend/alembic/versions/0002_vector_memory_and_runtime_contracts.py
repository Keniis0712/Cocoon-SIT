"""vector memory and runtime contracts

Revision ID: 0002_vector_memory_and_runtime_contracts
Revises: 0001_initial
Create Date: 2026-04-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.models.vector import PGVector


revision = "0002_vector_memory_and_runtime_contracts"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column(
        "embedding_providers",
        sa.Column("kind", sa.String(length=64), nullable=False, server_default="local_cpu"),
    )
    op.add_column(
        "embedding_providers",
        sa.Column("secret_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "action_dispatches",
        sa.Column("debounce_until", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "failed_rounds",
        sa.Column("event_type", sa.String(length=32), nullable=False, server_default="unknown"),
    )

    op.create_table(
        "memory_embeddings",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("memory_chunk_id", sa.String(length=64), nullable=False),
        sa.Column("embedding_provider_id", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding", PGVector(), nullable=True),
        sa.Column("usage_json", sa.JSON(), nullable=False),
        sa.Column("meta_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["embedding_provider_id"],
            ["embedding_providers.id"],
            name="fk_memory_embeddings_embedding_provider_id_embedding_providers",
        ),
        sa.ForeignKeyConstraint(
            ["memory_chunk_id"],
            ["memory_chunks.id"],
            name="fk_memory_embeddings_memory_chunk_id_memory_chunks",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_memory_embeddings"),
        sa.UniqueConstraint("memory_chunk_id", name="uq_memory_embeddings_memory_chunk_id"),
    )

    op.alter_column("embedding_providers", "kind", server_default=None)
    op.alter_column("failed_rounds", "event_type", server_default=None)


def downgrade() -> None:
    op.drop_table("memory_embeddings")
    op.drop_column("failed_rounds", "event_type")
    op.drop_column("action_dispatches", "debounce_until")
    op.drop_column("embedding_providers", "secret_encrypted")
    op.drop_column("embedding_providers", "kind")
