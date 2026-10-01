# Database migrations

Alembic revision files are stored permanently in `alembic/versions`. Commit
every generated revision to version control; do not edit an applied revision.

Create a new migration after changing the SQLAlchemy models:

```bash
make migration message="describe schema change"
```

Review the generated `upgrade()` and `downgrade()` functions before applying
it. Apply all pending migrations:

```bash
make migrate
```

Show the current database revision and the complete revision history:

```bash
make migration-current
make migration-history
```

Revert exactly one revision:

```bash
make downgrade
```

For an explicit revision, use its archived revision identifier:

```bash
docker compose exec api alembic downgrade <revision_id>
docker compose exec api alembic upgrade <revision_id>
```

Downgrading a migration can delete schema objects and data. Take a database
backup before reverting migrations in any environment that contains valuable
data.
