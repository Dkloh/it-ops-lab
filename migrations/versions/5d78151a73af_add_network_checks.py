"""add registered network targets and observations"""

import sqlalchemy as sa
from alembic import op

revision = "5d78151a73af"
down_revision = "e57f984a4626"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "check_targets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("service_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("check_type", sa.String(length=10), nullable=False),
        sa.Column("host", sa.String(length=253), nullable=False),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("scheme", sa.String(length=5), nullable=True),
        sa.Column("path", sa.String(length=2048), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("check_type IN ('DNS', 'TCP', 'HTTP')", name="ck_target_type"),
        sa.CheckConstraint("port IS NULL OR (port >= 1 AND port <= 65535)", name="ck_target_port"),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_check_targets_service_id", "check_targets", ["service_id"], unique=False)
    op.create_table(
        "check_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=10), nullable=False),
        sa.Column("duration_ms", sa.Double(), nullable=False),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("outcome IN ('success', 'failure')", name="ck_check_outcome"),
        sa.ForeignKeyConstraint(
            ["target_id"],
            ["check_targets.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_check_results_target_checked",
        "check_results",
        ["target_id", "checked_at"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_check_results_target_checked", table_name="check_results")
    op.drop_table("check_results")
    op.drop_index("ix_check_targets_service_id", table_name="check_targets")
    op.drop_table("check_targets")
