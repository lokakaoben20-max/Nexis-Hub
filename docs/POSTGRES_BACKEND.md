# PostgreSQL backend foundation — not yet activated

This is a separate, opt-in SQLAlchemy 2 / Alembic foundation. Existing SQLite bot and in-memory FastAPI routes are unchanged.

- Install: `pip install -r requirements-postgres.txt`
- Set `NEXIS_DATABASE_URL` to a dedicated **test** database URL with the `postgresql+psycopg://` scheme. Never commit credentials.
- Run `alembic current` to verify connectivity, **not** `alembic upgrade head` against production.
- No schema migration revision is defined yet: the nine SQLite tables and V5 identities require explicit model mapping and review first.
- The previous migration trial was successful only against disposable PostgreSQL with synthetic data; it did not establish a Neon connection.
- Do not connect financial endpoints to this foundation until transactional tests and reconciliation are complete.
