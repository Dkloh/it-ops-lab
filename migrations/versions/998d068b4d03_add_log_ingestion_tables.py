"""add log ingestion tables"""

import sqlalchemy as sa
from alembic import op

revision = "998d068b4d03"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "log_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("service_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("accepted_count", sa.Integer(), nullable=False),
        sa.Column("rejected_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_log_batches_service_id"), "log_batches", ["service_id"], unique=False)
    op.create_table(
        "ingestion_errors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["log_batches.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ingestion_errors_batch_id"), "ingestion_errors", ["batch_id"], unique=False
    )
    op.create_table(
        "log_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("severity", sa.String(length=10), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["log_batches.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_log_events_batch_id"), "log_events", ["batch_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_log_events_batch_id"), table_name="log_events")
    op.drop_table("log_events")
    op.drop_index(op.f("ix_ingestion_errors_batch_id"), table_name="ingestion_errors")
    op.drop_table("ingestion_errors")
    op.drop_index(op.f("ix_log_batches_service_id"), table_name="log_batches")
    op.drop_table("log_batches")
