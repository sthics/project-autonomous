# Database Design Best Practices

## Schema Design
- Start with SQLite for MVPs; plan migration path to PostgreSQL.
- Use integer primary keys with autoincrement.
- Add `created_at` and `updated_at` timestamps to every table.
- Use foreign keys with ON DELETE constraints (CASCADE for children, RESTRICT for references).
- Normalize to 3NF minimum; denormalize only with measured performance justification.

## Naming Conventions
- Tables: plural snake_case (`work_orders`, `customer_contacts`).
- Columns: singular snake_case (`first_name`, `created_at`).
- Indexes: `idx_{table}_{columns}` (`idx_work_orders_status_date`).
- Foreign keys: `{referenced_table_singular}_id` (`customer_id`).

## Indexing
- Always index foreign keys.
- Add composite indexes for frequent WHERE + ORDER BY combinations.
- Use partial indexes for filtered queries (e.g., `WHERE status = 'active'`).
- Monitor query plans; don't add speculative indexes.

## Migrations
- Use Alembic (Python) or Prisma (Node) for all schema changes.
- Every migration must be reversible (include downgrade).
- Never modify data in schema migrations; use separate data migrations.
- Test migrations against a copy of production-like data before applying.

## Security
- Always use parameterized queries — never string-interpolate SQL.
- Validate and sanitize all user inputs before they reach the database.
- Store passwords with bcrypt/argon2, never plaintext or simple hashes.
- Encrypt PII columns at rest when required by the domain.

## SQLite-Specific
- Enable WAL mode for concurrent read performance: `PRAGMA journal_mode=WAL`.
- Enable foreign key enforcement: `PRAGMA foreign_keys=ON`.
- Use `TEXT` for dates in ISO-8601 format.
- Keep database file in the project's `data/` directory, never in `src/`.
