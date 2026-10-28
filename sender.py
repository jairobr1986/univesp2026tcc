"""
Envio da PTS por e-mail e WhatsApp.

E-mail: usa smtplib (biblioteca padrão do Python) — funciona imediatamente,
sem dependências externas, desde que você configure um servidor SMTP no .env
(ex: Gmail com "senha de app", ou qualquer outro provedor).

WhatsApp: usa a API do Twilio, que exige uma conta (tem sandbox gratuito para
testes) e, para anexar o PDF, exige que o arquivo esteja acessível por uma URL
pública (o Twilio busca o arquivo nessa URL) — em desenvolvimento local isso
normalmente requer um túnel público (ex: ngrok); em produção, o próprio domínio
do servidor já resolve isso.
"""
import os
import smtplib
import ipaddress
import ssl
from urllib.parse import urlsplit
from email.message import EmailMessage


def enviar_email(destinatario: str, assunto: str, corpo: str, pdf_bytes: bytes, pdf_filename: str):
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASS"]
    remetente = os.environ.get("SMTP_FROM", user)

    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = remetente
    msg["To"] = destinatario
    msg.set_content(corpo)
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=pdf_filename)

    with smtplib.SMTP(host, port, timeout=20) as server:
        server.starttls(context=ssl.create_default_context())
        server.login(user, password)
        server.send_message(msg)


def enviar_whatsapp(numero_destino: str, mensagem: str, media_url: str = None):
    # import feito aqui dentro para que o app funcione mesmo sem a lib "twilio"
    # instalada, caso a pessoa só queira usar o envio por e-mail
    from twilio.rest import Client

    obrigatorias = ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM")
    ausentes = [nome for nome in obrigatorias if not os.environ.get(nome, "").strip()]
    if ausentes:
        raise ValueError(
            "WhatsApp nao configurado. Preencha no arquivo .env: "
            + ", ".join(ausentes) + ". Reinicie o servidor depois de salvar."
        )
    sid, token, remetente = (os.environ[nome].strip() for nome in obrigatorias)

    url = urlsplit(media_url or "")
    host = url.hostname or ""
    local = host.lower() == "localhost" or host.lower().endswith(".localhost")
    try:
        local = local or not ipaddress.ip_address(host).is_global
    except ValueError:
        pass
    if url.scheme != "https" or not host or local or url.username or url.password:
        raise ValueError(
            "Configure PUBLIC_BASE_URL no .env com o endereco publico do servidor. "
            "O Twilio nao consegue baixar o PDF de localhost ou de um IP da rede local."
        )

    digitos = "".join(ch for ch in numero_destino if ch.isdigit())
    if len(digitos) <= 11:
        digitos = "55" + digitos  # assume Brasil se não vier com código de país
    if not 10 <= len(digitos) <= 15 or digitos.startswith("0"):
        raise ValueError("Numero de WhatsApp invalido. Informe codigo do pais, DDD e numero.")

    client = Client(sid, token)
    kwargs = {"from_": remetente, "to": f"whatsapp:+{digitos}"}
    kwargs["body"] = mensagem
    if media_url:
        kwargs["media_url"] = [media_url]
    return client.messages.create(**kwargs).sid
