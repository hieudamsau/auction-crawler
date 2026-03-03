"""Add auction_category to auction_items (Luật Đấu giá 5 nhóm BĐS).

Revision ID: 20250301_ac
Revises:
Create Date: 2025-03-01

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20250301_ac"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "auction_items",
        sa.Column("auction_category", sa.String(50), nullable=True),
    )
    op.create_index(
        "idx_auction_category",
        "auction_items",
        ["auction_category"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_auction_category", table_name="auction_items")
    op.drop_column("auction_items", "auction_category")
