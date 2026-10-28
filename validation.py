"""Validação das regras no servidor e normalização das evidências recebidas."""
import base64
import binascii
import io
import re
import warnings
from datetime import date, datetime

from PIL import Image, ImageOps, UnidentifiedImageError

from catalog import CHECKLISTS, EPI_COMUM

ROLES = ("emitente", "executante", "supervisor")
MAX_IMAGE_BYTES = 350_000


def text(value, name, limit=300, required=True):
    if not isinstance(value, str) or len(value.strip()) > limit or (required and not value.strip()):
        raise ValueError(f"{name}: informe um texto válido (até {limit} caracteres).")
    if any(ord(c) < 32 and c not in "\n\r\t" for c in value):
        raise ValueError(f"{name}: caracteres inválidos.")
    return value.strip()


def image(value, signature=False):
    if not isinstance(value, str) or len(value) > MAX_IMAGE_BYTES * 4 // 3 + 100:
        raise ValueError("Imagem ausente ou maior que 350 KB.")
    match = re.fullmatch(r"data:image/(png|jpeg);base64,([A-Za-z0-9+/=\s]+)", value)
    if not match:
        raise ValueError("Envie uma imagem PNG ou JPEG em base64.")
    try:
        raw = base64.b64decode(match[2], validate=True)
        if len(raw) > MAX_IMAGE_BYTES:
            raise ValueError("Imagem maior que 350 KB.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as probe:
                if probe.format not in ("PNG", "JPEG"):
                    raise ValueError("Formato de imagem inválido.")
                if not (16 <= probe.width <= 2048 and 16 <= probe.height <= 2048):
                    raise ValueError("Dimensões da imagem devem estar entre 16 e 2048 pixels.")
                probe.load()
                normalized = ImageOps.exif_transpose(probe).convert("RGBA")
        background = Image.new("RGBA", normalized.size, "white")
        background.alpha_composite(normalized)
        normalized = background.convert("RGB")
        if signature:
            dark = normalized.convert("L").point(lambda p: 255 if p < 180 else 0)
            box = dark.getbbox()
            pixels = dark.histogram()[255]
            if (not box or box[2] - box[0] < 12 or box[3] - box[1] < 4
                    or not 30 <= pixels <= normalized.width * normalized.height * .45):
                raise ValueError("Assinatura vazia ou insuficiente. Desenhe a assinatura.")
        normalized.thumbnail((640, 480))
        output = io.BytesIO()
        normalized.save(output, "JPEG", quality=78, optimize=True)
        return output.getvalue(), "image/jpeg"
    except (UnidentifiedImageError, OSError, binascii.Error, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise ValueError("Imagem inválida ou danificada.") from exc


def signature(data, now):
    if not isinstance(data, dict):
        raise ValueError("Todas as assinaturas são obrigatórias.")
    result = {"nome": text(data.get("nome"), "Nome do signatário", 120),
              "dataHora": now, "recebidaEm": now}
    reported = data.get("dataHora")
    if reported is not None:
        if type(reported) is not int or not now - 24 * 3600_000 <= reported <= now + 300_000:
            raise ValueError("Horário do dispositivo inválido; confira a data do celular.")
        result["dataHoraDispositivo"] = reported
    for key in ("imagem", "foto"):
        result[key] = image(data.get(key), signature=key == "imagem")
    return result


def checklist(value, count, label):
    expected = {str(i) for i in range(count)}
    if not isinstance(value, dict) or set(value) != expected or any(v is not True for v in value.values()):
        raise ValueError(f"Confirme todos os itens de {label}.")
    return value


def permit(data, now, today):
    if not isinstance(data, dict):
        raise ValueError("O corpo JSON deve ser um objeto.")
    category = data.get("categoria")
    if not isinstance(category, str) or category not in CHECKLISTS:
        raise ValueError("Categoria inválida.")
    result = {"categoria": category}
    for name, limit in (("local", 300), ("empresa", 200), ("descricao", 5000), ("equipe", 3000)):
        result[name] = text(data.get(name), name, limit)
    try:
        issued = date.fromisoformat(text(data.get("dataEmissao"), "Data de emissão", 10))
        start = datetime.fromisoformat(text(data.get("validadeInicio"), "Início da validade", 16))
        end = datetime.fromisoformat(text(data.get("validadeFim"), "Fim da validade", 16))
        if start.tzinfo or end.tzinfo or start >= end or issued != today or start.date() != issued:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError("Emissão deve ser hoje; a validade deve começar na emissão e terminar após o início.")
    result.update(dataEmissao=issued.isoformat(), validadeInicio=start.isoformat(timespec="minutes"),
                  validadeFim=end.isoformat(timespec="minutes"))
    result["checklistRisco"] = checklist(data.get("checklistRisco"), len(CHECKLISTS[category]), "segurança")
    result["checklistEpi"] = checklist(data.get("checklistEpi"), len(EPI_COMUM), "EPIs")
    signatures = data.get("assinaturas")
    if not isinstance(signatures, dict) or set(signatures) != set(ROLES):
        raise ValueError("As três assinaturas são obrigatórias.")
    result["assinaturas"] = {role: signature(signatures[role], now) for role in ROLES}
    contacts = data.get("contatosEnvio", [])
    if not isinstance(contacts, list) or len(contacts) > 3:
        raise ValueError("Cadastre até três contatos.")
    result["contatosEnvio"] = []
    for contact in contacts:
        if not isinstance(contact, dict) or contact.get("tipo") not in ("email", "whatsapp"):
            raise ValueError("Tipo de contato inválido.")
        value = text(contact.get("valor", ""), "Contato", 254, required=False)
        if not value:
            result["contatosEnvio"].append({"tipo": contact["tipo"], "valor": ""})
            continue
        if contact["tipo"] == "email":
            if not re.fullmatch(r"[^\s@<>\r\n]+@[^\s@<>\r\n]+\.[^\s@<>\r\n]+", value):
                raise ValueError("E-mail inválido.")
        else:
            value = re.sub(r"\D", "", value)
            if len(value) in (10, 11):
                value = "55" + value
            if not re.fullmatch(r"[1-9]\d{9,14}", value):
                raise ValueError("WhatsApp inválido: informe país, DDD e número.")
        result["contatosEnvio"].append({"tipo": contact["tipo"], "valor": value})
    return result
