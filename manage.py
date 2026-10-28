"""Configuração e manutenção locais. Nunca executa migração no import da API."""
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import uuid

from dotenv import load_dotenv, set_key
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from catalog import CHECKLISTS, EPI_COMUM
from database import audit, evidence, init_schema, make_engine, permits, sequences, upsert
from validation import image

ROOT = Path(__file__).resolve().parent


def setup():
    env = ROOT / ".env"
    load_dotenv(env)
    username = input("Usuário (sem espaços): ").strip().lower()
    if not re.fullmatch(r"[a-z0-9_.-]{3,60}", username):
        raise ValueError("Use de 3 a 60 letras, números, ponto, hífen ou sublinhado.")
    name = input("Nome para exibição: ").strip()
    role = input("Perfil [admin/operador/consulta] (admin): ").strip() or "admin"
    if role not in ("admin", "operador", "consulta"):
        raise ValueError("Perfil inválido.")
    password = getpass.getpass("Senha (mínimo 10 caracteres): ")
    if len(password) < 10 or len(password) > 256 or password != password.strip():
        raise ValueError("Use entre 10 e 256 caracteres sem espaços nas extremidades.")
    if password != getpass.getpass("Repita a senha: "):
        raise ValueError("As senhas não coincidem.")
    users = json.loads(os.environ.get("APP_USERS", "{}"))
    users[username] = {"name": name or username, "role": role, "password_hash": generate_password_hash(password)}
    if not os.environ.get("SECRET_KEY"):
        set_key(str(env), "SECRET_KEY", secrets.token_hex(32))
    set_key(str(env), "APP_USERS", json.dumps(users, ensure_ascii=False))
    print("Acesso salvo no .env. Reinicie o servidor. Não compartilhe nem versione esse arquivo.")


def import_legacy(engine, source):
    """Importa uma única vez sem modificar o arquivo de origem nem fingir validação retroativa."""
    path = Path(source).resolve()
    if not path.is_file():
        raise ValueError("Banco legado não encontrado.")
    legacy = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    legacy.row_factory = sqlite3.Row
    try:
        rows = legacy.execute("SELECT * FROM pts ORDER BY created_at").fetchall()
    finally:
        legacy.close()
    imported = skipped = 0
    # Uma transação: qualquer falha desfaz a importação completa.
    with engine.begin() as conn:
        for row in rows:
            original = dict(row)
            source_key = "legacy:" + hashlib.sha256(str(path).encode()).hexdigest()[:12] + ":" + str(row["id"])
            if conn.execute(select(permits.c.id).where(permits.c.request_id == source_key)).first():
                skipped += 1
                continue
            category = row["categoria"]
            if category not in CHECKLISTS:
                raise ValueError(f"Categoria inválida no registro legado {row['id']}; nenhuma alteração foi gravada.")
            ident = uuid.uuid4().hex
            number = row["numero"] or "LEGADO-" + ident[:12]
            if conn.execute(select(permits.c.id).where(permits.c.numero == number)).first():
                number += "-LEGADO-" + ident[:8]
            moment = int(row["created_at"] or 0)
            parsed = re.fullmatch(r"PTS-([A-Z]+)-(\d{4})-(\d+)", row["numero"] or "")
            if parsed:
                key = category + "-" + parsed[2]
                number_value = int(parsed[3])
                from sqlalchemy import case
                upsert(conn, sequences, {"key": key, "value": number_value}, sequences.c.key,
                       {"value": case((sequences.c.value < number_value, number_value), else_=sequences.c.value)})
            record = {"id": ident, "numero": number, "categoria": category,
                      "status": row["status"] if row["status"] in ("aberta", "encerrada") else "cancelada",
                      "createdAt": moment, "updatedAt": int(row["updated_at"] or moment),
                      "legado": True, "idLegado": row["id"], "numeroLegado": row["numero"],
                      "criadaPor": "importacao-legado", "fuso": "America/Sao_Paulo",
                      "checklistVersao": "legado-sem-versao-original",
                      "checklistTextos": {"risco": CHECKLISTS[category], "epi": EPI_COMUM}}
            for old, new in (("data_emissao", "dataEmissao"), ("local", "local"), ("empresa", "empresa"),
                             ("descricao", "descricao"), ("validade_inicio", "validadeInicio"),
                             ("validade_fim", "validadeFim"), ("equipe", "equipe")):
                record[new] = row[old] or ""
            for old, new, fallback in (("checklist_risco", "checklistRisco", {}), ("checklist_epi", "checklistEpi", {}),
                                       ("assinaturas", "assinaturas", {}), ("contatos_envio", "contatosEnvio", []),
                                       ("encerramento", "encerramento", None)):
                record[new] = json.loads(row[old]) if row[old] else fallback
            conn.execute(permits.insert().values(id=ident, numero=number, categoria=category, status=record["status"],
                local=record["local"], empresa=record["empresa"], created_at=moment, updated_at=record["updatedAt"],
                owner="importacao-legado", request_id=source_key,
                request_hash=hashlib.sha256(json.dumps(original, sort_keys=True).encode()).hexdigest(), record="{}"))
            for sig in [*record["assinaturas"].values(), record["encerramento"]]:
                if not sig:
                    continue
                # dataHora legada continua identificada como fornecida pelo dispositivo.
                sig["dataHoraDispositivo"] = sig.get("dataHora")
                sig["recebidaEm"] = None
                sig["legado"] = True
                for key in ("imagem", "foto"):
                    if not sig.get(key):
                        continue
                    raw, mime = image(sig[key])
                    eid = uuid.uuid4().hex
                    conn.execute(evidence.insert().values(id=eid, permit_id=ident, mime=mime, content=raw))
                    sig[key] = "/api/evidencias/" + eid
            from sqlalchemy import update
            conn.execute(update(permits).where(permits.c.id == ident).values(record=json.dumps(record, ensure_ascii=False)))
            conn.execute(audit.insert().values(id=uuid.uuid4().hex, permit_id=ident, actor="importacao-legado",
                action="importacao_legado", at=int(__import__('time').time()*1000),
                details=json.dumps({"idLegado": row["id"], "snapshot": "Catálogo do código legado; versão original desconhecida"})))
            imported += 1
    print(f"Importados: {imported}; já existentes: {skipped}. Banco de origem preservado.")


def main():
    parser = argparse.ArgumentParser(description="Manutenção do protótipo PTS")
    parser.add_argument("command", choices=("setup", "init-db", "import-legacy", "backup-sqlite"))
    parser.add_argument("path", nargs="?")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    if args.command == "setup":
        setup()
        return
    engine = make_engine()
    if args.command == "init-db":
        init_schema(engine)
        print("Banco inicializado (esquema versão 1).")
    elif args.command == "import-legacy":
        init_schema(engine)
        import_legacy(engine, args.path or str(ROOT / "pts.db"))
    else:
        if engine.dialect.name != "sqlite":
            raise ValueError("Para PostgreSQL use pg_dump; consulte o README.")
        target = Path(args.path or "backups/pts-backup.db").resolve()
        if target.exists():
            raise ValueError("O destino já existe. Escolha outro nome para preservar o backup anterior.")
        target.parent.mkdir(parents=True, exist_ok=True)
        source = Path(engine.url.database).resolve()
        if not source.is_file():
            raise ValueError("Banco de origem não encontrado.")
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src, sqlite3.connect(target) as dst:
            src.backup(dst)
        print("Backup criado. Guarde-o em local privado.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, sqlite3.Error) as exc:
        raise SystemExit(str(exc))
