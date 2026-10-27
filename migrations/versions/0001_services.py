"""Create the service inventory."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "services",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("environment", sa.String(50), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("name", "environment", name="uq_service_name_environment"),
    )


def downgrade():
    op.drop_table("services")
