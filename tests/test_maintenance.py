import hashlib
import json
from pathlib import Path
import sqlite3

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from catalog import CHECKLISTS
from database import evidence, init_schema, make_engine, next_number, permits
from manage import import_legacy


def legacy_database(path, payload):
    columns = ("id numero categoria data_emissao local empresa descricao validade_inicio validade_fim equipe "
               "checklist_risco checklist_epi assinaturas contatos_envio status encerramento created_at updated_at").split()
    record = {
        "id": "antigo", "numero": "PTS-ALT-2026-001", "categoria": payload["categoria"],
        "data_emissao": payload["dataEmissao"], "local": payload["local"], "empresa": payload["empresa"],
        "descricao": payload["descricao"], "validade_inicio": payload["validadeInicio"], "validade_fim": payload["validadeFim"],
        "equipe": payload["equipe"], "checklist_risco": json.dumps(payload["checklistRisco"]),
        "checklist_epi": json.dumps(payload["checklistEpi"]), "assinaturas": json.dumps(payload["assinaturas"]),
        "contatos_envio": "[]", "status": "aberta", "encerramento": None,
        "created_at": 1_700_000_000_000, "updated_at": 1_700_000_000_000}
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE pts (" + ",".join(name + " TEXT" for name in columns) + ")")
        conn.execute("INSERT INTO pts VALUES (" + ",".join("?" for _ in columns) + ")", tuple(record[name] for name in columns))


def test_legacy_import_is_private_repeatable_and_preserves_source(application, payload, tmp_path):
    source = tmp_path / "old.db"
    legacy_database(source, payload)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    engine = application.extensions["db"]
    import_legacy(engine, source)
    import_legacy(engine, source)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    with engine.begin() as conn:
        rows = conn.execute(select(permits)).mappings().all()
        assert len(rows) == 1
        record = json.loads(rows[0]["record"])
        assert record["legado"] is True
        assert record["assinaturas"]["emitente"]["recebidaEm"] is None
        assert record["assinaturas"]["emitente"]["foto"].startswith("/api/evidencias/")
        assert len(conn.execute(select(evidence)).all()) == 6
        assert next_number(conn, "altura", 2026) == 2


def test_bad_legacy_image_rolls_back(application, payload, tmp_path):
    source = tmp_path / "bad.db"
    payload["assinaturas"]["emitente"]["foto"] = "invalid"
    legacy_database(source, payload)
    with pytest.raises(ValueError):
        import_legacy(application.extensions["db"], source)
    with application.extensions["db"].connect() as conn:
        assert not conn.execute(select(permits)).all()
        assert not conn.execute(select(evidence)).all()


def test_schema_idempotent_and_postgres_types(application):
    engine = application.extensions["db"]
    init_schema(engine)
    init_schema(engine)
    ddl = str(CreateTable(permits).compile(dialect=postgresql.dialect()))
    assert "created_at BIGINT" in ddl
    ddl = str(CreateTable(evidence).compile(dialect=postgresql.dialect()))
    assert "BYTEA" in ddl


def test_sqlite_forbidden_on_vercel(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    with pytest.raises(RuntimeError):
        make_engine("sqlite:///test.db")


def test_neon_url_uses_psycopg_without_connecting():
    engine = make_engine("postgresql://demo:fake@invalid.example/test?sslmode=require")
    assert engine.dialect.driver == "psycopg"
    assert engine.url.query["sslmode"] == "require"
    engine.dispose()


def test_setup_creates_hashed_users_and_keeps_existing_key(tmp_path, monkeypatch):
    from dotenv import dotenv_values
    from werkzeug.security import check_password_hash
    import manage
    monkeypatch.setattr(manage, "ROOT", tmp_path)
    monkeypatch.delenv("APP_USERS", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    answers = iter(["colega", "Pessoa da Equipe", "operador"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.setattr(manage.getpass, "getpass", lambda _: "senha-longa-teste")
    manage.setup()
    values = dotenv_values(tmp_path / ".env")
    user = json.loads(values["APP_USERS"])["colega"]
    assert len(values["SECRET_KEY"]) >= 32
    assert check_password_hash(user["password_hash"], "senha-longa-teste")
    assert "senha-longa-teste" not in (tmp_path / ".env").read_text()
    # Evita deixar a configuração temporária no ambiente do restante dos testes.
    monkeypatch.delenv("APP_USERS", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)


def test_backup_sqlite_can_be_restored(application, client, payload, tmp_path, monkeypatch):
    import manage
    import sys
    from test_api import create
    create(client, payload)
    target = tmp_path / "backup.db"
    monkeypatch.setattr(manage, "make_engine", lambda: application.extensions["db"])
    monkeypatch.setattr(sys, "argv", ["manage.py", "backup-sqlite", str(target)])
    manage.main()
    with sqlite3.connect(target.as_uri()+"?mode=ro", uri=True) as conn:
        assert conn.execute("SELECT COUNT(*) FROM permits").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0] == 6
    with pytest.raises(ValueError, match="destino"):
        manage.main()
