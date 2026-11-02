from urllib.parse import urlsplit, parse_qs
from itsdangerous import TimestampSigner
from sqlalchemy import select
from database import audit
from conftest import login
from test_api import create


def test_share_link_private_creation_public_download(application, client, payload, signature):
    record = create(client, payload).json
    route = f'/api/pts/{record["id"]}/link-pdf'
    anonymous = application.test_client()
    assert anonymous.post(route).status_code == 401
    assert login(application, 'consulta').post(route, json={}).status_code == 403
    assert client.post(route, json={}, headers={'X-CSRF-Token': 'wrong'}).status_code == 403
    response = client.post(route, json={})
    assert response.status_code == 200
    assert response.json['expiresIn'] == 900
    link = response.json['url']
    downloaded = anonymous.get(link)
    assert downloaded.status_code == 200
    assert downloaded.data.startswith(b'%PDF')
    assert downloaded.headers['Cache-Control'] == 'no-store'
    assert 'attachment' in downloaded.headers['Content-Disposition']
    assert anonymous.get(link+'x').status_code == 403
    assert anonymous.get(f'/api/pts/{record["id"]}/pdf').status_code == 401
    with application.extensions['db'].connect() as conn:
        event = conn.execute(select(audit).where(audit.c.action=='link_pdf_criado')).mappings().one()
        token = parse_qs(urlsplit(link).query)['token'][0]
        assert token not in event['details']
    assert client.put(f'/api/pts/{record["id"]}/encerrar', json=signature).status_code == 200
    assert anonymous.get(link).status_code == 403


def test_expired_share_link(application, client, payload, monkeypatch):
    record = create(client, payload).json
    link = client.post(f'/api/pts/{record["id"]}/link-pdf', json={}).json['url']
    original = TimestampSigner.get_timestamp
    with monkeypatch.context() as patch:
        patch.setattr(TimestampSigner, 'get_timestamp', lambda self: original(self)+901)
        assert application.test_client().get(link).status_code == 403
