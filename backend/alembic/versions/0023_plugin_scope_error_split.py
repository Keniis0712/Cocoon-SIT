"""split plugin scope validation and runtime errors

Revision ID: 0023_plugin_scope_error_split
Revises: 0022_cocoon_context_anchor
Create Date: 2026-04-26 10:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0023_plugin_scope_error_split"
down_revision: str | None = "0022_cocoon_context_anchor"
branch_labels = None
depends_on = None


def _migrate_scope_table(table_name: str) -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    table = sa.Table(table_name, metadata, autoload_with=bind)
    bind.execute(
        table.update().values(
            runtime_error_text=table.c.error_text,
            runtime_error_at=table.c.error_at,
        )
    )


def upgrade() -> None:
    for table_name in ("plugin_user_configs", "plugin_chat_group_configs"):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(sa.Column("validation_error_text", sa.Text(), nullable=True))
            batch_op.add_column(
                sa.Column("validation_error_at", sa.DateTime(timezone=False), nullable=True)
            )
            batch_op.add_column(sa.Column("runtime_error_text", sa.Text(), nullable=True))
            batch_op.add_column(
                sa.Column("runtime_error_at", sa.DateTime(timezone=False), nullable=True)
            )
        _migrate_scope_table(table_name)
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_column("error_text")
            batch_op.drop_column("error_at")


def downgrade() -> None:
    for table_name in ("plugin_user_configs", "plugin_chat_group_configs"):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(sa.Column("error_text", sa.Text(), nullable=True))
            batch_op.add_column(sa.Column("error_at", sa.DateTime(timezone=False), nullable=True))

        bind = op.get_bind()
        metadata = sa.MetaData()
        table = sa.Table(table_name, metadata, autoload_with=bind)
        bind.execute(
            table.update().values(
                error_text=sa.func.coalesce(
                    table.c.validation_error_text,
                    table.c.runtime_error_text,
                ),
                error_at=sa.func.coalesce(
                    table.c.validation_error_at,
                    table.c.runtime_error_at,
                ),
            )
        )

        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_column("runtime_error_at")
            batch_op.drop_column("runtime_error_text")
            batch_op.drop_column("validation_error_at")
            batch_op.drop_column("validation_error_text")
