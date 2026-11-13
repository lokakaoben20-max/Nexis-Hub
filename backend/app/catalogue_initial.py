"""Contenu initial du catalogue : services et communes servies.

Figé : c'est exactement ce que la migration `f2a3b4c5d6e7` écrit dans une
vraie base, et ce que `database.init_db()` écrit dans une base de test, pour
que les deux soient identiques. Repris tel quel de l'ancien `db.py`, qui le
recréait à chaque démarrage du bot.

Ne jamais modifier ces listes pour changer le catalogue : une modification
passe par une nouvelle migration, qui porte ses propres valeurs. Ce fichier
reste le point de départ.
"""

from decimal import Decimal

import sqlalchemy as sa

# (clé, nom fr, nom ln, nom en, catégorie, icône, module, visite, frais de visite USD)
SERVICES = (
    ("service_plomberie", "Plomberie", "Plomberie", "Plumbing", "Maison", "🔧", "B", True, Decimal("5.00")),
    ("service_electricite", "Electricité", "Electricité", "Electricity", "Maison", "⚡", "B", True, Decimal("5.00")),
    ("service_climatisation", "Climatisation", "Climatisation", "Air conditioning", "Maison", "❄️", "B", True, Decimal("5.00")),
    ("service_informatique", "Informatique", "Informatique", "IT support", "Digital", "💻", "A", False, Decimal("0.00")),
    ("service_graphisme", "Graphisme", "Graphisme", "Design", "Digital", "🎨", "A", False, Decimal("0.00")),
    ("service_coiffure", "Coiffure", "Coiffure", "Hairdressing", "Beauté", "✂️", "A", False, Decimal("0.00")),
    ("service_nettoyage", "Nettoyage", "Nettoyage", "Cleaning", "Maison", "🧹", "A", False, Decimal("0.00")),
    ("service_jardinage", "Jardinage", "Jardinage", "Gardening", "Maison", "🌿", "A", False, Decimal("0.00")),
    ("service_autre", "Autre service", "Service mosusu", "Other service", "Autre", "➕", "A", False, Decimal("0.00")),
)

# Communes proposées aujourd'hui par le bot et la Mini App, dans leur ordre.
COMMUNES = (
    "Gombe",
    "Kinshasa",
    "Limete",
    "Ngaliema",
    "Lemba",
    "Kalamu",
    "Barumbu",
    "Lingwala",
    "Autre commune",
)

_services = sa.table(
    "services",
    sa.column("key", sa.String),
    sa.column("name_fr", sa.String),
    sa.column("name_ln", sa.String),
    sa.column("name_en", sa.String),
    sa.column("category", sa.String),
    sa.column("icon_emoji", sa.String),
    sa.column("module", sa.String),
    sa.column("requires_inspection", sa.Boolean),
    sa.column("visit_fee_usd", sa.Numeric(10, 2)),
    sa.column("position", sa.Integer),
    sa.column("is_active", sa.Boolean),
)
_communes = sa.table("communes", sa.column("name", sa.String), sa.column("position", sa.Integer))


def remplir(connection) -> None:
    """Écrit le catalogue initial dans des tables vides."""
    connection.execute(
        _services.insert(),
        [
            {
                "key": key,
                "name_fr": name_fr,
                "name_ln": name_ln,
                "name_en": name_en,
                "category": category,
                "icon_emoji": icon,
                "module": module,
                "requires_inspection": inspection,
                "visit_fee_usd": fee,
                "position": position,
                "is_active": True,
            }
            for position, (key, name_fr, name_ln, name_en, category, icon, module, inspection, fee) in enumerate(SERVICES, 1)
        ],
    )
    connection.execute(_communes.insert(), [{"name": name, "position": position} for position, name in enumerate(COMMUNES, 1)])
