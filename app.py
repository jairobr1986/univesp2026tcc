"""API de PTS autenticada com PostgreSQL/Neon ou SQLite local."""
import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from datetime import datetime, timedelta
from io import BytesIO
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, abort, g, jsonify, render_template, request, send_file, send_from_directory, session
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import and_, case, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

from catalog import CATS, CHECKLISTS, CHECKLIST_VERSION, EPI_COMUM
from database import attempts, audit, evidence, init_schema, make_engine, next_number, permits, upsert
from pdf_generator import gerar_pdf
import validation

load_dotenv()
TZ = ZoneInfo("America/Sao_Paulo")
CODES = {"altura": "ALT", "confinado": "CONF", "eletricidade": "ELE", "quente": "QNT"}


def now_ms():
    return int(time.time() * 1000)


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def create_app(config=None):
    app = Flask(__name__, static_folder="public/static", static_url_path="/static")
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY"), DATABASE_URL=os.environ.get("DATABASE_URL"),
        USERS=json.loads(os.environ.get("APP_USERS", "{}")), MAX_CONTENT_LENGTH=3_500_000,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_SECURE=bool(os.environ.get("VERCEL")) or os.environ.get("COOKIE_SECURE") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8), AUTO_SEND=os.environ.get("ENABLE_AUTO_SEND") == "1")
    if config:
        app.config.update(config)
    if not isinstance(app.config["USERS"], dict) or any(
        not isinstance(user, dict) or user.get("role") not in ("admin", "operador", "consulta")
        or not isinstance(user.get("password_hash"), str)
        for user in app.config["USERS"].values()
    ):
        raise RuntimeError("APP_USERS deve conter usuários com role e password_hash válidos.")
    if os.environ.get("VERCEL") and (not app.secret_key or len(app.secret_key) < 32):
        raise RuntimeError("Configure SECRET_KEY com pelo menos 32 caracteres na Vercel.")
    if not app.secret_key:
        if os.environ.get("VERCEL"):
            raise RuntimeError("Configure SECRET_KEY na Vercel.")
        app.secret_key = secrets.token_hex(32)
        app.logger.warning("Execute python manage.py setup para configurar o acesso local.")
    engine = make_engine(app.config.get("DATABASE_URL"))
    app.extensions["db"] = engine
    dummy_hash = generate_password_hash(secrets.token_hex(20))

    def log(conn, ident, action, details=None):
        conn.execute(audit.insert().values(id=uuid.uuid4().hex, permit_id=ident,
            actor=g.user["username"], action=action, at=now_ms(), details=encode(details or {})))

    def require_role(*roles):
        if g.user["role"] not in roles:
            abort(403, description="Seu perfil não permite esta operação.")

    def payload():
        data = request.get_json()
        if not isinstance(data, dict):
            raise ValueError("O corpo JSON deve ser um objeto.")
        return data

    def get_record(conn, ident, lock=False):
        stmt = select(permits).where(permits.c.id == ident)
        if lock:
            stmt = stmt.with_for_update()
        row = conn.execute(stmt).mappings().first()
        if not row:
            abort(404, description="PTS não encontrada.")
        return json.loads(row["record"])

    def save(conn, record):
        conn.execute(update(permits).where(permits.c.id == record["id"]).values(
            record=encode(record), status=record["status"], updated_at=record["updatedAt"]))

    def store_signature(conn, ident, sig):
        for key in ("imagem", "foto"):
            raw, mime = sig[key]
            eid = uuid.uuid4().hex
            conn.execute(evidence.insert().values(id=eid, permit_id=ident, mime=mime, content=raw))
            sig[key] = "/api/evidencias/" + eid
        return sig

    def pdf_record(conn, record):
        for sig in [*record.get("assinaturas", {}).values(), record.get("encerramento")]:
            if not sig:
                continue
            for key in ("imagem", "foto"):
                eid = sig.get(key, "").rsplit("/", 1)[-1]
                row = conn.execute(select(evidence).where(and_(
                    evidence.c.id == eid, evidence.c.permit_id == record["id"]))).mappings().first()
                sig[key] = ("data:" + row["mime"] + ";base64," + base64.b64encode(row["content"]).decode()) if row else None
        return record

    @app.before_request
    def protect():
        if not request.path.startswith("/api/"):
            return
        g.user = None
        username = session.get("username")
        user = app.config["USERS"].get(username) if username else None
        if isinstance(user, dict) and user.get("role") in ("admin", "operador", "consulta"):
            fingerprint = hashlib.sha256(user.get("password_hash", "").encode()).hexdigest()
            if hmac.compare_digest(session.get("auth_version", ""), fingerprint):
                g.user = {"username": username, "name": user.get("name", username), "role": user["role"]}
        public = request.endpoint in ("auth_session", "login", "health")
        signed_pdf = request.endpoint == "pdf" and request.args.get("token")
        if not public and not g.user and not signed_pdf:
            abort(401, description="Entre para acessar o aplicativo.")
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            expected = session.get("csrf", "")
            if not expected or not hmac.compare_digest(request.headers.get("X-CSRF-Token", ""), expected):
                abort(403, description="Sessão expirada. Atualize a página e tente novamente.")

    @app.after_request
    def headers(response):
        response.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer", "Permissions-Policy": "camera=(self), microphone=(), geolocation=()",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; media-src 'self' blob:; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"})
        if request.path.startswith("/api/") or request.path in ("/", "/index.html", "/sw.js"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(ValueError)
    def validation_error(error):
        return jsonify(erro=str(error)), 400

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(erro=error.description), error.code

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        app.logger.error("Falha no banco: %s", type(error).__name__)
        return jsonify(erro="Banco indisponível. Tente novamente; confira a configuração se o erro persistir."), 503

    @app.errorhandler(Exception)
    def unexpected_error(error):
        app.logger.error("Falha interna: %s", type(error).__name__)
        return jsonify(erro="Não foi possível concluir a operação. Tente novamente."), 500

    @app.get("/api/health")
    def health():
        with engine.connect() as conn:
            conn.execute(select(permits.c.id).limit(1))
        return jsonify(ok=True)

    @app.get("/api/auth/session")
    def auth_session():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return jsonify(user=g.user, csrf=session["csrf"], configured=bool(app.config["USERS"]))

    @app.post("/api/auth/login")
    def login():
        data = payload()
        username = validation.text(data.get("username"), "Usuário", 100).lower()
        password = validation.text(data.get("password"), "Senha", 256)
        key = hashlib.sha256((username + app.secret_key).encode()).hexdigest()
        moment = now_ms()
        with engine.begin() as conn:
            expired = attempts.c.window < moment - 900_000
            upsert(conn, attempts, {"key": key, "count": 1, "window": moment}, attempts.c.key,
                   {"count": case((expired, 1), else_=attempts.c.count + 1),
                    "window": case((expired, moment), else_=attempts.c.window)})
            count = conn.execute(select(attempts.c.count).where(attempts.c.key == key)).scalar_one()
            conn.execute(delete(attempts).where(attempts.c.window < moment - 86_400_000))
        if count > 8:
            abort(429, description="Muitas tentativas. Aguarde 15 minutos.")
        user = app.config["USERS"].get(username, {})
        valid = check_password_hash(user.get("password_hash", dummy_hash), password)
        if not valid or user.get("role") not in ("admin", "operador", "consulta"):
            abort(401, description="Usuário ou senha inválidos.")
        with engine.begin() as conn:
            conn.execute(delete(attempts).where(attempts.c.key == key))
        session.clear()
        session.update(username=username, csrf=secrets.token_urlsafe(32),
                       auth_version=hashlib.sha256(user["password_hash"].encode()).hexdigest())
        session.permanent = True
        return jsonify(user={"username": username, "name": user.get("name", username), "role": user["role"]}, csrf=session["csrf"])

    @app.post("/api/auth/logout")
    def logout():
        session.clear()
        return jsonify(ok=True)

    @app.get("/api/catalogo")
    def catalog():
        return jsonify(categorias=CATS, checklists=CHECKLISTS, epi=EPI_COMUM, versao=CHECKLIST_VERSION,
                       hoje=datetime.now(TZ).date().isoformat(), autoSend=app.config["AUTO_SEND"])

    @app.get("/api/pts")
    def list_pts():
        try:
            page = max(1, int(request.args.get("page", 1)))
            limit = min(50, max(1, int(request.args.get("limit", 20))))
        except ValueError:
            raise ValueError("Paginação inválida.")
        stmt = select(permits.c.id, permits.c.numero, permits.c.categoria, permits.c.status,
                      permits.c.local, permits.c.empresa, permits.c.created_at, permits.c.updated_at)
        conditions = []
        for field in ("categoria", "status"):
            value = request.args.get(field)
            if value and value != "todas":
                conditions.append(permits.c[field] == value)
        query = request.args.get("q", "").strip()[:200]
        if query:
            conditions.append(or_(*(col.icontains(query, autoescape=True) for col in
                                    (permits.c.local, permits.c.numero, permits.c.empresa))))
        with engine.connect() as conn:
            total = conn.execute(select(func.count()).select_from(permits).where(*conditions)).scalar_one()
            rows = conn.execute(stmt.where(*conditions).order_by(permits.c.created_at.desc(), permits.c.id)
                                .offset((page - 1) * limit).limit(limit)).mappings().all()
        items = [{**dict(row), "createdAt": row["created_at"], "updatedAt": row["updated_at"]} for row in rows]
        return jsonify(items=items, page=page, limit=limit, total=total)

    @app.post("/api/pts")
    def create_pts():
        require_role("admin", "operador")
        data = payload()
        request_id = validation.text(request.headers.get("Idempotency-Key"), "Identificador da emissão", 80)
        request_id = g.user["username"] + ":" + request_id
        digest = hashlib.sha256(encode(data).encode()).hexdigest()
        with engine.connect() as conn:
            previous = conn.execute(select(permits).where(permits.c.request_id == request_id)).mappings().first()
        if previous:
            if previous["request_hash"] != digest:
                abort(409, description="Esta emissão já foi processada com outros dados. Abra uma nova PTS.")
            return jsonify(json.loads(previous["record"]))
        moment = now_ms()
        record = validation.permit(data, moment, datetime.now(TZ).date())
        ident = uuid.uuid4().hex
        record.update(id=ident, status="aberta", encerramento=None, createdAt=moment, updatedAt=moment,
            criadaPor=g.user["username"], checklistVersao=CHECKLIST_VERSION,
            checklistTextos={"risco": CHECKLISTS[record["categoria"]], "epi": EPI_COMUM}, fuso="America/Sao_Paulo")
        try:
            with engine.begin() as conn:
                year = datetime.now(TZ).year
                sequence = next_number(conn, record["categoria"], year)
                record["numero"] = f'PTS-{CODES[record["categoria"]]}-{year}-{sequence:04d}'
                conn.execute(permits.insert().values(id=ident, numero=record["numero"], categoria=record["categoria"],
                    status="aberta", local=record["local"], empresa=record["empresa"], created_at=moment,
                    updated_at=moment, owner=g.user["username"], request_id=request_id, request_hash=digest, record="{}"))
                record["assinaturas"] = {role: store_signature(conn, ident, sig) for role, sig in record["assinaturas"].items()}
                save(conn, record)
                log(conn, ident, "emissao", {"numero": record["numero"], "checklistVersao": CHECKLIST_VERSION})
        except IntegrityError:
            with engine.connect() as conn:
                previous = conn.execute(select(permits).where(permits.c.request_id == request_id)).mappings().first()
            if previous and previous["request_hash"] == digest:
                return jsonify(json.loads(previous["record"]))
            abort(409, description="Conflito na emissão. Atualize e tente novamente.")
        return jsonify(record), 201

    @app.get("/api/pts/<ident>")
    def detail(ident):
        with engine.connect() as conn:
            return jsonify(get_record(conn, ident))

    @app.put("/api/pts/<ident>/encerrar")
    def close(ident):
        require_role("admin", "operador")
        data = payload()
        sig = validation.signature(data, now_ms())
        sig["observacoes"] = validation.text(data.get("observacoes", ""), "Observações", 5000, False)
        with engine.begin() as conn:
            changed = conn.execute(update(permits).where(and_(permits.c.id == ident, permits.c.status == "aberta"))
                                   .values(status="encerrada"))
            record = get_record(conn, ident)
            if changed.rowcount != 1:
                abort(409, description="Somente uma PTS aberta pode ser encerrada.")
            record.update(status="encerrada", encerramento=store_signature(conn, ident, sig), updatedAt=now_ms())
            record["updatedAt"] = max(record["updatedAt"], record["createdAt"] + 1)
            save(conn, record)
            log(conn, ident, "encerramento")
        return jsonify(record)

    @app.post("/api/pts/<ident>/cancelar")
    def cancel(ident):
        require_role("admin")
        reason = validation.text(payload().get("motivo"), "Motivo do cancelamento", 1000)
        with engine.begin() as conn:
            changed = conn.execute(update(permits).where(and_(permits.c.id == ident, permits.c.status == "aberta"))
                                   .values(status="cancelada"))
            record = get_record(conn, ident)
            if changed.rowcount != 1:
                abort(409, description="Somente uma PTS aberta pode ser cancelada.")
            record.update(status="cancelada", updatedAt=now_ms(),
                cancelamento={"motivo": reason, "autor": g.user["username"], "dataHora": now_ms()})
            record["updatedAt"] = max(record["updatedAt"], record["createdAt"] + 1)
            save(conn, record)
            log(conn, ident, "cancelamento", {"motivo": reason})
        return jsonify(record)

    @app.delete("/api/pts/<ident>")
    def refuse_delete(ident):
        abort(405, description="O histórico é preservado. Utilize o cancelamento com motivo.")

    @app.get("/api/pts/<ident>/historico")
    def history(ident):
        with engine.connect() as conn:
            get_record(conn, ident)
            rows = conn.execute(select(audit).where(audit.c.permit_id == ident).order_by(audit.c.at, audit.c.id)).mappings().all()
        return jsonify([{**dict(row), "details": json.loads(row["details"])} for row in rows])

    @app.get("/api/evidencias/<eid>")
    def media(eid):
        with engine.connect() as conn:
            row = conn.execute(select(evidence).where(evidence.c.id == eid)).mappings().first()
        if not row:
            abort(404)
        return send_file(BytesIO(row["content"]), mimetype=row["mime"], max_age=0)

    @app.get("/api/pts/<ident>/pdf")
    def pdf(ident):
        token = request.args.get("token")
        if token:
            try:
                signed = URLSafeTimedSerializer(app.secret_key, salt="pts-pdf").loads(token, max_age=900)
                if signed.get("id") != ident:
                    abort(403)
            except BadSignature:
                abort(403, description="Link do PDF inválido ou expirado.")
        elif not g.user:
            abort(401)
        with engine.connect() as conn:
            record = get_record(conn, ident)
            if token and signed.get("updatedAt") != record["updatedAt"]:
                abort(403, description="Documento atualizado; solicite um novo link.")
            content = gerar_pdf(pdf_record(conn, record))
        return send_file(BytesIO(content), mimetype="application/pdf", as_attachment=True,
                         download_name=record["numero"] + ".pdf", max_age=0)

    @app.post("/api/pts/<ident>/enviar")
    def send(ident):
        require_role("admin", "operador")
        if not app.config["AUTO_SEND"]:
            abort(409, description="Envio automático desativado. Baixe ou compartilhe o PDF pelo dispositivo.")
        index = payload().get("contato_index")
        with engine.begin() as conn:
            record = get_record(conn, ident, lock=True)
            contacts = record.get("contatosEnvio", [])
            if type(index) is not int or not 0 <= index < len(contacts) or not contacts[index].get("valor"):
                raise ValueError("Contato inválido.")
            recent = conn.execute(select(audit.c.at).where(and_(audit.c.permit_id == ident,
                audit.c.action == "envio_solicitado", audit.c.at > now_ms() - 60_000))).first()
            if recent:
                abort(429, description="Aguarde um minuto antes de solicitar outro envio.")
            log(conn, ident, "envio_solicitado", {"contato": index})
            pdf_bytes = gerar_pdf(pdf_record(conn, record))
        contact = contacts[index]
        message = f'Permissão de Trabalho Seguro {record["numero"]} - {record["local"]}.'
        try:
            from sender import enviar_email, enviar_whatsapp
            provider_id = None
            if contact["tipo"] == "email":
                enviar_email(contact["valor"], record["numero"], message, pdf_bytes, record["numero"] + ".pdf")
            else:
                base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
                token = URLSafeTimedSerializer(app.secret_key, salt="pts-pdf").dumps({"id": ident, "updatedAt": record["updatedAt"]})
                provider_id = enviar_whatsapp(contact["valor"], message, media_url=f"{base}/api/pts/{ident}/pdf?token={token}")
        except Exception as exc:
            with engine.begin() as conn:
                log(conn, ident, "envio_falhou", {"contato": index, "tipoErro": type(exc).__name__})
            abort(502, description="O provedor não confirmou o envio. Confira a configuração ou compartilhe manualmente.")
        with engine.begin() as conn:
            log(conn, ident, "envio_aceito_provedor", {"contato": index, "protocolo": provider_id})
        return jsonify(ok=True, mensagem="Envio aceito pelo provedor; entrega não confirmada.")

    @app.get("/")
    @app.get("/index.html")
    def index():
        return render_template("index.html")

    @app.get("/sw.js")
    def service_worker():
        return send_from_directory(os.path.join(app.root_path, "public"), "sw.js")

    @app.cli.command("init-db")
    def init_db_command():
        init_schema(engine)
        print("Esquema versão 1 inicializado; tabelas antigas preservadas.")

    return app


app = create_app()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PTS — servidor local")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    init_schema(app.extensions["db"])
    print(f"Abra http://localhost:{args.port}/")
    app.run(host=args.host, port=args.port, debug=False)
