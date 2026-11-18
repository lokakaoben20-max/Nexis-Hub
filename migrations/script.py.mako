"""\u0024{message}

Revision ID: \u0024{up_revision}
Revises: \u0024{down_revision | comma,n}
Create Date: \u0024{create_date}
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
\u0024{imports if imports else ""}

revision: str = \u0024{repr(up_revision)}
down_revision: Union[str, None] = \u0024{repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = \u0024{repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = \u0024{repr(depends_on)}


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
