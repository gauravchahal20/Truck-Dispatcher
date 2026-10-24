"""add_carrier_usdot_unique_index

Revision ID: b1a2c3d4e5f6
Revises: 4756b857e0d9
Create Date: 2026-10-24 23:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1a2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '4756b857e0d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Creates partial unique index on carrier USDOT."""
    # Enforces uniqueness for CARRIERs having non-empty USDOT.
    # Shippers and unassigned leads with NULL or empty USDOT are not constrained.
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_companies_carrier_usdot
        ON companies (usdot)
        WHERE usdot IS NOT NULL AND TRIM(usdot) != '' AND UPPER(lead_type) = 'CARRIER'
    """)


def downgrade() -> None:
    """Removes carrier USDOT unique index."""
    op.execute("DROP INDEX IF EXISTS uq_companies_carrier_usdot")
