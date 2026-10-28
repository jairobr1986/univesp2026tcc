"""Persistência comum a SQLite local e PostgreSQL/Neon, sem DDL no import."""
import os
from pathlib import Path

from sqlalchemy import (BigInteger, Column, ForeignKey, Integer, LargeBinary,
                        MetaData, String, Table, Text, create_engine, event)
from sqlalchemy.pool import NullPool

metadata = MetaData()
permits = Table(
    "permits", metadata,
    Column("id", String(32), primary_key=True),
    Column("numero", String(80), nullable=False, unique=True),
    Column("categoria", String(20), nullable=False, index=True),
    Column("status", String(20), nullable=False, index=True),
    Column("local", Text, nullable=False), Column("empresa", Text, nullable=False),
    Column("created_at", BigInteger, nullable=False, index=True),
    Column("updated_at", BigInteger, nullable=False),
    Column("owner", String(100), nullable=False),
    Column("request_id", String(200), nullable=False, unique=True),
    Column("request_hash", String(64), nullable=False),
    Column("record", Text, nullable=False),
)
sequences = Table("permit_sequences", metadata,
                  Column("key", String(60), primary_key=True),
                  Column("value", Integer, nullable=False))
evidence = Table("evidence", metadata,
                 Column("id", String(64), primary_key=True),
                 Column("permit_id", ForeignKey("permits.id"), nullable=False, index=True),
                 Column("mime", String(30), nullable=False),
                 Column("content", LargeBinary, nullable=False))
audit = Table("audit_events", metadata,
              Column("id", String(32), primary_key=True),
              Column("permit_id", ForeignKey("permits.id"), nullable=False, index=True),
              Column("actor", String(100), nullable=False),
              Column("action", String(50), nullable=False),
              Column("at", BigInteger, nullable=False),
              Column("details", Text, nullable=False))
attempts = Table("login_attempts", metadata,
                 Column("key", String(64), primary_key=True),
                 Column("count", Integer, nullable=False),
                 Column("window", BigInteger, nullable=False))
schema = Table("schema_versions", metadata,
               Column("version", Integer, primary_key=True))


def make_engine(url=None):
    url = url or os.environ.get("DATABASE_URL")
    if not url:
        if os.environ.get("VERCEL"):
            raise RuntimeError("Configure DATABASE_URL do PostgreSQL na Vercel.")
        url = "sqlite:///" + str(Path(__file__).with_name("pts-v2.db"))
    if url.startswith(("postgres://", "postgresql://")):
        url = "postgresql+psycopg://" + url.split("://", 1)[1]
    if os.environ.get("VERCEL") and not url.startswith("postgresql+psycopg://"):
        raise RuntimeError("O deploy exige PostgreSQL persistente.")
    options = {"poolclass": NullPool}
    if url.startswith("sqlite"):
        options["connect_args"] = {"timeout": 20, "check_same_thread": False}
    else:
        options["connect_args"] = {"connect_timeout": 10}
    engine = create_engine(url, **options)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    return engine


def init_schema(engine):
    """Migração inicial idempotente; tabelas legadas pts ficam intactas."""
    from sqlalchemy import select
    metadata.create_all(engine)
    with engine.begin() as conn:
        if conn.execute(select(schema.c.version)).first() is None:
            conn.execute(schema.insert().values(version=1))


def upsert(conn, table, values, key, updates):
    if conn.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    stmt = insert(table).values(**values)
    return conn.execute(stmt.on_conflict_do_update(index_elements=[key], set_=updates))


def next_number(conn, category, year):
    """UPSERT serializa concorrência por categoria/ano, sem contar permissões."""
    key = f"{category}-{year}"
    if conn.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    stmt = insert(sequences).values(key=key, value=1)
    return conn.execute(stmt.on_conflict_do_update(
        index_elements=[sequences.c.key], set_={"value": sequences.c.value + 1}
    ).returning(sequences.c.value)).scalar_one()
