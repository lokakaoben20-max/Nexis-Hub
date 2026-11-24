"""Conserve le nom et la commune choisis par le client de l'app."""

import sqlalchemy as sa
from alembic import op

revision = "c1d2e3f4a5b6"
down_revision = "b0c1d2e3f4a5"
branch_labels = None
depends_on = None


# Les huit autres communes étaient déjà au catalogue. L'entrée historique
# « Autre commune » est conservée pour les profils et missions existants.
ADDITIONAL_COMMUNES = (
    "Bandalungwa", "Bumbu", "Kasa-Vubu", "Kimbanseke", "Kintambo", "Kisenso",
    "Makala", "Maluku", "Masina", "Matete", "Mont-Ngafula", "N'djili",
    "Ngaba", "Ngiri-Ngiri", "N'sele", "Selembao",
)


def upgrade() -> None:
    communes = sa.table("communes", sa.column("name", sa.String(64)), sa.column("position", sa.Integer()))
    existing = dict(op.get_bind().execute(sa.select(communes.c.name, communes.c.position)).all())
    last_position = max(existing.values(), default=0)
    missing = [name for name in ADDITIONAL_COMMUNES if name not in existing]
    if missing:
        op.bulk_insert(communes, [
            {"name": name, "position": last_position + offset}
            for offset, name in enumerate(missing, start=1)
        ])
    op.add_column("client_profiles", sa.Column("last_name", sa.String(255), nullable=True))
    op.add_column("client_profiles", sa.Column("preferred_commune", sa.String(64), nullable=True))
    op.create_foreign_key(
        "fk_client_profiles_preferred_commune", "client_profiles", "communes", ["preferred_commune"], ["name"]
    )


def downgrade() -> None:
    # Les nouvelles communes peuvent déjà être utilisées par des prestataires.
    op.drop_constraint("fk_client_profiles_preferred_commune", "client_profiles", type_="foreignkey")
    op.drop_column("client_profiles", "preferred_commune")
    op.drop_column("client_profiles", "last_name")
