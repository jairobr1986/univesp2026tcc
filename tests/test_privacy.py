import base64
import json
import pytest
from sqlalchemy import select, update

from database import evidence, permits
from evidence_crypto import EvidenceCipher, EvidenceError, PREFIX
from privacy_maintenance import encrypt_existing, purge_expired, set_hold
from test_api import create


@pytest.mark.parametrize('value', [None, '', 'nao-base64!', base64.b64encode(b'a'*16).decode()])
def test_missing_or_invalid_key_is_rejected(value):
    with pytest.raises(EvidenceError):
        EvidenceCipher(value)


def test_cipher_tamper_binding_and_nonce():
    cipher = EvidenceCipher(base64.b64encode(b'a'*32).decode())
    encrypted = cipher.encrypt(b'sensitive photo', 'e1', 'p1', 'image/jpeg')
    assert encrypted != cipher.encrypt(b'sensitive photo', 'e1', 'p1', 'image/jpeg')
    assert cipher.decrypt(encrypted, 'e1', 'p1', 'image/jpeg') == b'sensitive photo'
    for blob, ident in ((encrypted[:-1]+bytes([encrypted[-1]^1]), 'e1'), (encrypted, 'e2')):
        with pytest.raises(EvidenceError):
            cipher.decrypt(blob, ident, 'p1', 'image/jpeg')
    with pytest.raises(EvidenceError):
        EvidenceCipher(base64.b64encode(b'b'*32).decode()).decrypt(encrypted, 'e1', 'p1', 'image/jpeg')
    with pytest.raises(EvidenceError):
        cipher.decrypt(b'plaintext', 'e1', 'p1', 'image/jpeg')


def test_encrypted_storage_and_migration(application, client, payload):
    record = create(client, payload).json
    engine = application.extensions['db']
    cipher = application.extensions['evidence_cipher']
    with engine.begin() as conn:
        row = conn.execute(select(evidence)).mappings().first()
        assert row['content'].startswith(PREFIX)
        raw = cipher.decrypt(row['content'], row['id'], row['permit_id'], row['mime'])
        assert raw.startswith(b'\xff\xd8\xff')
        conn.execute(update(evidence).where(evidence.c.id == row['id']).values(content=raw))
    assert client.get('/api/evidencias/'+row['id']).status_code == 503
    assert encrypt_existing(engine, cipher)['a_criptografar'] == 1
    assert encrypt_existing(engine, cipher, True)['a_criptografar'] == 1
    assert encrypt_existing(engine, cipher, True)['a_criptografar'] == 0
    assert client.get('/api/evidencias/'+row['id']).data == raw
    assert client.get('/api/pts/'+record['id']+'/pdf').data.startswith(b'%PDF')


def test_migration_rolls_back_on_corrupt_ciphertext(application, client, payload):
    create(client, payload)
    engine = application.extensions['db']
    cipher = application.extensions['evidence_cipher']
    with engine.begin() as conn:
        rows = conn.execute(select(evidence).order_by(evidence.c.id)).mappings().all()
        first, last = rows[0], rows[-1]
        raw = cipher.decrypt(first['content'], first['id'], first['permit_id'], first['mime'])
        conn.execute(update(evidence).where(evidence.c.id==first['id']).values(content=raw))
        conn.execute(update(evidence).where(evidence.c.id==last['id']).values(content=last['content'][:-1]))
    with pytest.raises(EvidenceError):
        encrypt_existing(engine, cipher, True)
    with engine.connect() as conn:
        assert conn.execute(select(evidence.c.content).where(evidence.c.id==first['id'])).scalar_one()==raw


def test_retention_dry_run_hold_and_delete(application, client, payload, signature):
    record = create(client, payload).json
    engine = application.extensions['db']
    future = record['createdAt'] + 100*86400_000
    assert purge_expired(engine, 30, now=future)['permissoes_elegiveis'] == 0
    assert client.put('/api/pts/'+record['id']+'/encerrar', json=signature).status_code==200
    assert purge_expired(engine,30,now=future)['permissoes_elegiveis']==1
    assert client.get('/api/pts/'+record['id']).status_code==200
    set_hold(engine, record['id'], True)
    assert purge_expired(engine,30,True, future)['permissoes_elegiveis']==0
    set_hold(engine, record['id'], False)
    assert purge_expired(engine,30,True,future)['permissoes_elegiveis']==1
    assert client.get('/api/pts/'+record['id']).status_code==404
    with engine.connect() as conn:
        assert not conn.execute(select(evidence)).all()
    with pytest.raises(ValueError):
        purge_expired(engine, 0, True)
