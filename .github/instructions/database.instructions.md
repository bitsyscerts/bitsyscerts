---
description: "Use when creating or modifying database migrations, SQLAlchemy models, Alembic files, or any file that defines or queries database tables. Enforces Alembic authoring rules, CT-scale index design, async session scoping, autovacuum guidance for high-churn tables, and retention-driven schema decisions."
applyTo: "src/**"
---

# Database Coding Standards

These rules apply to every file that touches the database schema or query layer:
`migrations/`, `database.py`, `models.py`, `repository.py`, and any file importing
`sqlalchemy` or `alembic`.

---

## Alembic Migration Authoring Rules

- Every migration MUST have a human-readable `revision`, `down_revision`, and a concise
  one-line description in the docstring.
- MUST NOT mix multiple unrelated schema changes in one migration. Each migration has a
  **single concern** (one table, one index, one constraint change).
- `CREATE INDEX` on large tables MUST use `CONCURRENTLY` to avoid locking production reads.
  Example:
  ```python
  op.execute(
      "CREATE INDEX CONCURRENTLY ix_hostnames_not_before "
      "ON hostnames (latest_cert_not_before DESC, id DESC)"
  )
  ```
- `CREATE INDEX CONCURRENTLY` **cannot run inside a transaction**. Migrations that use it
  MUST set `transactional_ddl = False` on the migration context, or be isolated in their
  own migration file with:

  ```python
  # In the migration file:
  from alembic import op

  def upgrade() -> None:
      op.execute("COMMIT")  # end the implicit transaction
      op.execute("CREATE INDEX CONCURRENTLY ...")
  ```

  Alternatively, use `op.get_context().configure(..., transaction_per_migration=False)`.

- `downgrade()` MUST be implemented for every migration. An empty `downgrade()` is a defect
  unless the migration is explicitly marked as non-reversible with a comment explaining why.
- MUST NOT use `op.execute()` with raw SQL that includes user-supplied values. Use
  parameterized statements.
- After authoring a migration, always run `alembic check` to confirm the generated SQL
  matches the intended ORM model state.

---

## SQLAlchemy Model Conventions

- ORM models MUST be defined with SQLAlchemy's declarative base (`DeclarativeBase`).
- Every table MUST have an explicit `__tablename__`.
- Primary keys MUST be explicitly typed. Prefer `BigInteger` for high-volume CT tables
  (hostnames, observations, outcomes) — `Integer` overflows at ~2 billion rows.
- All timestamp columns MUST be `TIMESTAMP WITH TIME ZONE` (`DateTime(timezone=True)`),
  never `TIMESTAMP WITHOUT TIME ZONE`.
- Foreign key constraints MUST have an explicit `ON DELETE` action. Default to `CASCADE`
  only when the child row has no independent meaning. Use `RESTRICT` or `SET NULL` otherwise.
- ORM models (SQLAlchemy) and API models (Pydantic) MUST be separate classes. MUST NOT use
  ORM models directly as Pydantic response models or vice versa.

---

## Index Design for CT-Scale Tables

CT ingestion tables (`hostnames`, `ct_log_observations`, `ct_entry_outcomes`,
`certificate_hostnames`) can reach tens of millions of rows. Index every column that
appears in a `WHERE`, `ORDER BY`, or `JOIN ON` clause in a production query path.

### Required indexes by table

| Table                   | Required Indexes                                                                                              | Rationale                                 |
| ----------------------- | ------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| `hostnames`             | `hostname` (B-tree unique); `(latest_cert_not_before DESC, id DESC)`; `(latest_cert_not_after DESC, id DESC)` | Search and keyset pagination sort columns |
| `ct_log_observations`   | `(log_source_id, log_index)` unique; `observed_at` (for time-range deletes)                                   | Deduplication + retention pruning         |
| `ct_entry_outcomes`     | `(log_source_id, log_index)` unique; `first_seen_at` (for time-range deletes)                                 | Same                                      |
| `certificate_hostnames` | `(fingerprint_sha256)`; `hostname_id`                                                                         | Join and lookup                           |
| `ingestion_errors`      | `(log_source_id, occurred_at)`                                                                                | Pruning and per-log diagnostics           |

### Index overhead reality

- For tables with unique B-tree indexes on high-cardinality CT columns, total
  **table + index size ≈ 2.0–2.5× the raw data size**. Do not use 1.35× as a multiplier
  in any storage estimate.
- GIN trigram indexes (used for hostname substring search) are 3–5× the size of the
  indexed column data. Account for this in storage projections.

---

## Async Session Scoping

- MUST use SQLAlchemy's `async_sessionmaker` with `expire_on_commit=False` to avoid
  lazy-load errors after `commit()`.
- Sessions MUST be scoped to a single request or a single CLI task invocation. MUST NOT
  share a session across multiple concurrent tasks or background workers.
- Use `async with session.begin():` for atomic write operations. MUST NOT call
  `session.commit()` manually inside a context that uses `session.begin()`.
- MUST NOT hold a session open across network I/O (e.g., while fetching from a CT log).
  Fetch data first, then open a session to write.
- Close sessions explicitly in CLI scripts — do not rely on garbage collection.

---

## Autovacuum Tuning for High-Churn Tables

CT ingestion tables that implement rolling-window retention (7-day observations, 7-day
outcomes) insert and delete millions of rows per day. PostgreSQL's default autovacuum
settings are tuned for OLTP workloads with much lower churn rates. Without tuning,
dead-tuple bloat accumulates and table files grow even when the logical row count is stable.

Apply these settings via a migration `ALTER TABLE ... SET (...)`:

| Table                 | Setting                           | Value   | Rationale                                     |
| --------------------- | --------------------------------- | ------- | --------------------------------------------- |
| `ct_log_observations` | `autovacuum_vacuum_scale_factor`  | `0.01`  | Vacuum when 1% of rows are dead (default 20%) |
| `ct_log_observations` | `autovacuum_analyze_scale_factor` | `0.005` | Analyze when 0.5% change                      |
| `ct_entry_outcomes`   | `autovacuum_vacuum_scale_factor`  | `0.01`  | Same rationale                                |
| `ct_entry_outcomes`   | `autovacuum_analyze_scale_factor` | `0.005` | Same                                          |

```python
# In a migration:
op.execute("""
    ALTER TABLE ct_log_observations SET (
        autovacuum_vacuum_scale_factor = 0.01,
        autovacuum_analyze_scale_factor = 0.005
    )
""")
```

---

## Retention-Driven Schema Rules

Every table created by a migration MUST have one of the following explicitly documented
in a comment in the migration file:

1. **Time-bounded:** "Pruned by `<pruner_function>` on a `<N>-day` rolling window."
2. **Bounded by foreign key cascade:** "Deleted automatically when parent `<table>` row is deleted."
3. **Configuration-bounded:** "Row count bounded by number of `<entity>` records (expected: ≤ N)."
4. **Audit trail with explicit limit:** "Pruned to `<N>` rows or `<N>` days by `<pruner_function>`."

A table with no documented retention policy is a defect. It MUST be fixed before the
migration is merged.

---

## Storage Projection Accuracy

When writing or updating storage projection code:

- Use `_DAILY_CT_ENTRIES_ESTIMATE = 12_000_000` (current global CT issuance rate).
  Do NOT use values below 8,000,000.
- Use `_INDEX_OVERHEAD_FACTOR = 2.2` for tables with unique B-tree indexes on CT columns.
  Do NOT use values below 2.0.
- Add a separate line-item for GIN trigram indexes (hostname search): estimate 3–5× the
  hostname column data size.
- Add 20–30% for MVCC dead-tuple bloat on high-churn tables, even with proper autovacuum.
- Label projections as estimates with a ±30% margin in any user-facing copy.
