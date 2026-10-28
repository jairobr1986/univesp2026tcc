import base64
import io
from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw
import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from catalog import CHECKLISTS, EPI_COMUM
from database import init_schema


@pytest.fixture
def application(tmp_path):
    password_hash = generate_password_hash("senha-teste-123")
    app = create_app({"TESTING": True, "SECRET_KEY": "chave-exclusiva-dos-testes",
                      "DATABASE_URL": "sqlite:///" + str(tmp_path / "test.db"),
                      "SESSION_COOKIE_SECURE": False,
                      "AUTO_SEND": False,
                      "USERS": {role: {"name": role, "role": role, "password_hash": password_hash}
                                for role in ("admin", "operador", "consulta")}})
    init_schema(app.extensions["db"])
    yield app
    app.extensions["db"].dispose()


def login(app, role="admin"):
    client = app.test_client()
    csrf = client.get("/api/auth/session").json["csrf"]
    response = client.post("/api/auth/login", json={"username": role, "password": "senha-teste-123"},
                           headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    client.environ_base["HTTP_X_CSRF_TOKEN"] = response.json["csrf"]
    return client


@pytest.fixture
def client(application):
    return login(application)


def data_image(signature=False):
    img = Image.new("RGB", (240, 100), "white" if signature else "#aa8877")
    if signature:
        ImageDraw.Draw(img).line([(10, 70), (50, 20), (80, 80), (150, 30), (220, 65)], fill="black", width=4)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


@pytest.fixture
def signature():
    return {"nome": "Pessoa de Teste", "imagem": data_image(True), "foto": data_image()}


@pytest.fixture
def payload(signature):
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat()
    return {"categoria": "altura", "dataEmissao": today, "local": "Galpão de teste", "empresa": "UNIVESP",
            "descricao": "Inspeção simulada", "equipe": "Pessoa Um\nPessoa Dois",
            "validadeInicio": today + "T08:00", "validadeFim": today + "T10:00",
            "checklistRisco": {str(i): True for i in range(len(CHECKLISTS["altura"]))},
            "checklistEpi": {str(i): True for i in range(len(EPI_COMUM))},
            "assinaturas": {role: dict(signature) for role in ("emitente", "executante", "supervisor")},
            "contatosEnvio": []}
