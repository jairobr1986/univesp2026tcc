import copy
import io
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

from itsdangerous import URLSafeTimedSerializer
from pypdf import PdfReader
import pytest
from sqlalchemy import select

from catalog import CHECKLISTS
from database import audit, evidence, permits
from conftest import data_image, login


def create(client, payload, key=None):
    return client.post("/api/pts", json=payload, headers={"Idempotency-Key": key or uuid.uuid4().hex})


def test_auth_csrf_logout_and_cookie(application):
    anonymous = application.test_client()
    assert anonymous.get("/api/pts").status_code == 401
    assert anonymous.post("/api/auth/login", json={}).status_code == 403
    client = login(application)
    assert client.post("/api/pts", json={}, headers={"X-CSRF-Token": "outro"}).status_code == 403
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/pts").status_code == 401


def test_password_change_revokes_session(application):
    client = login(application)
    application.config["USERS"]["admin"]["password_hash"] = "revogado"
    assert client.get("/api/pts").status_code == 401


def test_login_rate_limit(application):
    client = application.test_client()
    token = client.get("/api/auth/session").json["csrf"]
    for _ in range(8):
        assert client.post("/api/auth/login", json={"username": "admin", "password": "errada"},
                           headers={"X-CSRF-Token": token}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "errada"},
                       headers={"X-CSRF-Token": token}).status_code == 429


@pytest.mark.parametrize("category", CHECKLISTS)
def test_full_lifecycle(client, payload, signature, category):
    payload["categoria"] = category
    payload["checklistRisco"] = {str(i): True for i in range(len(CHECKLISTS[category]))}
    response = create(client, payload)
    assert response.status_code == 201, response.json
    record = response.json
    assert record["assinaturas"]["emitente"]["recebidaEm"] == record["createdAt"]
    assert record["checklistTextos"]["risco"] == CHECKLISTS[category]
    media = record["assinaturas"]["emitente"]["foto"]
    assert client.get(media).status_code == 200
    listing = client.get("/api/pts").json
    assert listing["total"] == 1
    assert "assinaturas" not in listing["items"][0]
    assert client.get(f'/api/pts/{record["id"]}/pdf').data.startswith(b"%PDF")
    response = client.put(f'/api/pts/{record["id"]}/encerrar', json=signature)
    assert response.status_code == 200
    assert client.put(f'/api/pts/{record["id"]}/encerrar', json=signature).status_code == 409
    assert client.post(f'/api/pts/{record["id"]}/cancelar', json={"motivo": "Teste"}).status_code == 409
    history = client.get(f'/api/pts/{record["id"]}/historico').json
    assert [event["action"] for event in history] == ["emissao", "encerramento"]


@pytest.mark.parametrize("field,value", [
    ("local", ""), ("empresa", ""), ("descricao", ""), ("equipe", ""), ("categoria", []),
    ("categoria", "outra"), ("checklistRisco", {}), ("checklistEpi", {}), ("assinaturas", {}),
    ("validadeFim", "2020-01-01T08:00"), ("dataEmissao", "2020-01-01"),
    ("contatosEnvio", [{"tipo": "email", "valor": "teste@example.com"}] * 4),
    ("contatosEnvio", [{"tipo": "outro", "valor": "x"}]),
    ("contatosEnvio", [{"tipo": "email", "valor": "invalid"}]),
    ("contatosEnvio", [{"tipo": "email", "valor": "x@y.com\r\nBcc: z@x.com"}]),
    ("contatosEnvio", [{"tipo": "whatsapp", "valor": "1"}]),
])
def test_required_validation(client, payload, field, value):
    payload[field] = value
    assert create(client, payload).status_code == 400
    assert client.get("/api/pts").json["total"] == 0


def test_exact_checklist_keys_and_booleans(client, payload):
    payload["checklistRisco"]["extra"] = True
    assert create(client, payload).status_code == 400
    del payload["checklistRisco"]["extra"]
    payload["checklistRisco"]["0"] = 1
    assert create(client, payload).status_code == 400


@pytest.mark.parametrize("value", [[], None, "texto", 42])
def test_json_shape(client, value):
    assert client.post("/api/pts", data=json.dumps(value), content_type="application/json").status_code == 400


def test_images_blank_and_timestamp(client, payload):
    payload["assinaturas"]["emitente"]["imagem"] = data_image()
    # Uniformly colored image cannot serve as a signature (see validator).
    assert create(client, payload).status_code == 400


@pytest.mark.parametrize("bad", ["data:image/svg+xml;base64,PHN2Zz4=", "data:image/png;base64,aA==", "x", "data:image/png;base64," + "A" * 500_000])
def test_bad_photos(client, payload, bad):
    payload["assinaturas"]["emitente"]["foto"] = bad
    assert create(client, payload).status_code == 400


def test_oversize_request(client):
    response = client.post("/api/pts", data=b"x" * 3_500_001, content_type="application/json")
    assert response.status_code == 413


def test_permissions_and_cancel_retains_media(application, client, payload):
    reader = login(application, "consulta")
    operator = login(application, "operador")
    assert create(reader, payload).status_code == 403
    record = create(operator, payload).json
    path = f'/api/pts/{record["id"]}'
    assert reader.get(path).status_code == 200
    assert operator.post(path + "/cancelar", json={"motivo": "Teste"}).status_code == 403
    assert reader.put(path + "/encerrar", json={}).status_code == 403
    assert client.delete(path).status_code == 405
    assert client.post(path + "/cancelar", json={}).status_code == 400
    assert client.post(path + "/cancelar", json={"motivo": "Erro na atividade informada"}).status_code == 200
    record = client.get(path).json
    assert record["status"] == "cancelada"
    assert client.get(record["assinaturas"]["emitente"]["foto"]).status_code == 200
    assert client.post(path + "/cancelar", json={"motivo": "Outro"}).status_code == 409


def test_idempotency_and_sequence(client, payload):
    first = create(client, payload, "same").json
    assert create(client, payload, "same").json["id"] == first["id"]
    changed = copy.deepcopy(payload)
    changed["local"] = "Outro"
    assert create(client, changed, "same").status_code == 409
    client.post(f'/api/pts/{first["id"]}/cancelar', json={"motivo": "Teste"})
    second = create(client, payload).json
    assert int(second["numero"].split("-")[-1]) == int(first["numero"].split("-")[-1]) + 1
    assert client.get("/api/pts").json["total"] == 2


def test_concurrent_emission(application, payload):
    def task(index):
        client = login(application)
        response = create(client, payload, "parallel-" + str(index))
        assert response.status_code == 201, response.json
        return response.json["numero"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        numbers = list(pool.map(task, range(8)))
    assert len(set(numbers)) == 8


def test_private_media_pdf_and_signed_link(application, client, payload):
    record = create(client, payload).json
    anonymous = application.test_client()
    path = f'/api/pts/{record["id"]}/pdf'
    assert anonymous.get(path).status_code == 401
    assert anonymous.get(record["assinaturas"]["emitente"]["foto"]).status_code == 401
    signer = URLSafeTimedSerializer(application.secret_key, salt="pts-pdf")
    token = signer.dumps({"id": record["id"], "updatedAt": record["updatedAt"]})
    assert anonymous.get(path + "?token=" + token).status_code == 200
    assert anonymous.get(path + "?token=invalid").status_code == 403
    wrong = signer.dumps({"id": "outro", "updatedAt": record["updatedAt"]})
    assert anonymous.get(path + "?token=" + wrong).status_code == 403
    client.post(f'/api/pts/{record["id"]}/cancelar', json={"motivo": "Teste"})
    assert anonymous.get(path + "?token=" + token).status_code == 403


def test_pdf_long_text_snapshot_and_escaping(client, payload):
    payload["descricao"] = ("Descrição de teste com acentuação & <marcação>. " * 100)[:4900]
    payload["equipe"] = "Pessoa Um\nPessoa Dois"
    payload["local"] = "W" * 290
    record = create(client, payload).json
    response = client.get(f'/api/pts/{record["id"]}/pdf')
    assert response.status_code == 200
    pdf = PdfReader(io.BytesIO(response.data))
    text = "\n".join(page.extract_text() for page in pdf.pages)
    assert len(pdf.pages) >= 3
    assert "Pessoa Dois" in text
    assert "<marcação>" in text
    assert record["checklistVersao"] in text
    assert "Página" in text
    assert "sem comparação" not in text or "biométric" in text


def test_pagination_search_and_no_sensitive_cache(client, payload):
    create(client, payload)
    payload["empresa"] = "Outra Empresa"
    create(client, payload)
    data = client.get("/api/pts?limit=1&page=2").json
    assert len(data["items"]) == 1 and data["total"] == 2
    assert client.get("/api/pts?q=Outra").json["total"] == 1
    assert client.get("/api/pts?q=%25").json["total"] == 0
    response = client.get("/api/pts")
    assert response.headers["Cache-Control"] == "no-store"
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]


def test_manual_share_default(client, payload):
    record = create(client, payload).json
    assert client.get("/api/catalogo").json["autoSend"] is False
    assert client.post(f'/api/pts/{record["id"]}/enviar', json={"contato_index": 0}).status_code == 409


def test_auto_send_failure_and_acceptance(application, client, payload, monkeypatch):
    application.config["AUTO_SEND"] = True
    payload["contatosEnvio"] = [{"tipo": "email", "valor": "destino@example.com"}]
    record = create(client, payload).json
    path = f'/api/pts/{record["id"]}/enviar'
    def fail(*args, **kwargs):
        raise RuntimeError("Segredo que não pode aparecer na resposta")
    monkeypatch.setattr("sender.enviar_email", fail)
    response = client.post(path, json={"contato_index": 0})
    assert response.status_code == 502
    assert b"Segredo" not in response.data
    assert client.post(path, json={"contato_index": 0}).status_code == 429
    with application.extensions["db"].begin() as conn:
        conn.execute(audit.delete().where(audit.c.action == "envio_solicitado"))
    monkeypatch.setattr("sender.enviar_email", lambda *args: None)
    assert client.post(path, json={"contato_index": 0}).status_code == 200
    events = client.get(f'/api/pts/{record["id"]}/historico').json
    assert any(event["action"] == "envio_aceito_provedor" for event in events)
