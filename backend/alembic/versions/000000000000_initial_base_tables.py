"""initial_base_tables

Revision ID: 000000000000
Revises: 
Create Date: 2026-10-22 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from app.models.entities import Base


# revision identifiers, used by Alembic.
revision: str = '000000000000'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Creates initial database schema if not already present."""
    conn = op.get_bind()
    # Create all base tables on fresh database
    Base.metadata.create_all(conn)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    Base.metadata.drop_all(conn)
