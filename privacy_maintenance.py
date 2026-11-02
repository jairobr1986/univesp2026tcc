"""Migração explícita e descarte por prazo aprovado, sem executar na importação."""
import json
import time
from sqlalchemy import delete, select, update
from database import audit, evidence, permits
from evidence_crypto import PREFIX


def encrypt_existing(engine, cipher, apply=False):
    changed = checked = 0
    with engine.begin() as conn:
        # Operar em janela de manutenção: não concorrer com descarte/importação.
        rows = conn.execute(select(evidence).order_by(evidence.c.id).with_for_update()).mappings()
        for row in rows:
            args = (row['id'], row['permit_id'], row['mime'])
            raw = bytes(row['content'])
            if raw.startswith(PREFIX):
                cipher.decrypt(raw, *args)  # Valida chave antes de confirmar a transação.
                checked += 1
            else:
                if not raw.startswith((b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff')):
                    raise ValueError('Conteúdo desconhecido; migração cancelada sem alterações.')
                encrypted = cipher.encrypt(raw, *args)
                assert cipher.decrypt(encrypted, *args) == raw
                if apply:
                    conn.execute(update(evidence).where(evidence.c.id == row['id']).values(content=encrypted))
                changed += 1
    return {'a_criptografar': changed, 'ja_verificadas': checked, 'aplicado': apply}


def purge_expired(engine, days, apply=False, now=None):
    if type(days) is not int or days < 1:
        raise ValueError('Defina um prazo aprovado, inteiro positivo, em RETENTION_DAYS.')
    cutoff = (int(time.time()*1000) if now is None else now) - days * 86400_000
    total = 0
    with engine.begin() as conn:
        rows = conn.execute(select(permits).where(
            permits.c.status.in_(['encerrada', 'cancelada']),
            permits.c.updated_at < cutoff).with_for_update()).mappings()
        for row in rows:
            if json.loads(row['record']).get('retentionHold'):
                continue
            if apply:
                for table in (evidence, audit):
                    conn.execute(delete(table).where(table.c.permit_id == row['id']))
                conn.execute(delete(permits).where(permits.c.id == row['id']))
            total += 1
    return {'permissoes_elegiveis': total, 'prazo_dias': days, 'aplicado': apply}


def set_hold(engine, ident, enabled):
    with engine.begin() as conn:
        row = conn.execute(select(permits).where(permits.c.id == ident).with_for_update()).mappings().first()
        if not row:
            raise ValueError('PTS não encontrada.')
        record = json.loads(row['record'])
        record['retentionHold'] = enabled
        conn.execute(update(permits).where(permits.c.id == ident).values(record=json.dumps(record, ensure_ascii=False)))
