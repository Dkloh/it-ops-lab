"""index log event investigation queries"""

from alembic import op

revision = "67136625fb8f"
down_revision = "998d068b4d03"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index(op.f("ix_log_events_batch_id"), table_name="log_events")
    op.create_index(
        "ix_log_events_batch_occurred", "log_events", ["batch_id", "occurred_at"], unique=False
    )
    op.create_index("ix_log_events_occurred", "log_events", ["occurred_at"], unique=False)
    op.create_index(
        "ix_log_events_severity_occurred", "log_events", ["severity", "occurred_at"], unique=False
    )


def downgrade():
    op.drop_index("ix_log_events_severity_occurred", table_name="log_events")
    op.drop_index("ix_log_events_occurred", table_name="log_events")
    op.drop_index("ix_log_events_batch_occurred", table_name="log_events")
    op.create_index(op.f("ix_log_events_batch_id"), "log_events", ["batch_id"], unique=False)
