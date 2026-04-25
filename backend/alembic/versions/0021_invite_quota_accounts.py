"""Add direct invite quota accounts."""

from __future__ import annotations

from collections import defaultdict

from alembic import op
import sqlalchemy as sa


revision = "0021_invite_quota_accounts"
down_revision = "0020_user_timezones"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invite_quota_accounts",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("remaining_quota", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_unlimited", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("target_type", "target_id", name="uq_invite_quota_accounts_target"),
    )

    bind = op.get_bind()
    metadata = sa.MetaData()
    grants = sa.Table("invite_quota_grants", metadata, autoload_with=bind)
    invites = sa.Table("invite_codes", metadata, autoload_with=bind)
    accounts = sa.Table("invite_quota_accounts", metadata, autoload_with=bind)

    granted_totals: dict[tuple[str, str], int] = defaultdict(int)
    unlimited_targets: set[tuple[str, str]] = set()
    consumed_totals: dict[tuple[str, str], int] = defaultdict(int)

    for row in bind.execute(
        sa.select(
            grants.c.target_type,
            grants.c.target_id,
            grants.c.quota,
            grants.c.is_unlimited,
        ).where(grants.c.revoked_at.is_(None))
    ):
        key = (str(row.target_type), str(row.target_id))
        if bool(row.is_unlimited):
            unlimited_targets.add(key)
        else:
            granted_totals[key] += int(row.quota or 0)

    for row in bind.execute(
        sa.select(
            invites.c.source_type,
            invites.c.source_id,
            invites.c.quota_total,
        ).where(
            invites.c.source_type.in_(("USER", "GROUP")),
            invites.c.source_id.is_not(None),
            invites.c.revoked_at.is_(None),
        )
    ):
        key = (str(row.source_type), str(row.source_id))
        consumed_totals[key] += int(row.quota_total or 0)

    now = sa.func.now()
    all_keys = set(granted_totals) | set(unlimited_targets) | set(consumed_totals)
    for index, (target_type, target_id) in enumerate(sorted(all_keys), start=1):
        bind.execute(
            accounts.insert().values(
                id=f"invite-quota-{index}",
                target_type=target_type,
                target_id=target_id,
                remaining_quota=max(granted_totals[(target_type, target_id)] - consumed_totals[(target_type, target_id)], 0),
                is_unlimited=(target_type, target_id) in unlimited_targets,
                created_at=now,
                updated_at=now,
            )
        )


def downgrade() -> None:
    op.drop_table("invite_quota_accounts")
