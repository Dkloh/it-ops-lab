"""add diagnostic runs findings and evidence"""

import sqlalchemy as sa
from alembic import op

revision = "e57f984a4626"
down_revision = "67136625fb8f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "diagnostic_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("ruleset_version", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('running', 'completed')", name="ck_run_status"),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["log_batches.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "findings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("rule_code", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("summary", sa.String(), nullable=False),
        sa.Column("explanation", sa.String(), nullable=False),
        sa.Column("suggested_action", sa.String(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.CheckConstraint("severity IN ('HIGH', 'MEDIUM')", name="ck_finding_severity"),
        sa.CheckConstraint("event_count > 0", name="ck_finding_event_count"),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["diagnostic_runs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "rule_code", name="uq_finding_run_rule"),
    )
    op.create_table(
        "finding_events",
        sa.Column("finding_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["log_events.id"],
        ),
        sa.ForeignKeyConstraint(
            ["finding_id"],
            ["findings.id"],
        ),
        sa.PrimaryKeyConstraint("finding_id", "event_id"),
    )


def downgrade():
    op.drop_table("finding_events")
    op.drop_table("findings")
    op.drop_table("diagnostic_runs")
