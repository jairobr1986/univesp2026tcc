"""PDF multipágina com textos históricos, equipe e evidências privadas."""
import base64
import io
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate,
                               Spacer, Table, TableStyle)

from catalog import CATS, CHECKLISTS, EPI_COMUM

FONT_DIR = Path(reportlab.__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("PTS", str(FONT_DIR / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("PTS-Bold", str(FONT_DIR / "VeraBd.ttf")))
pdfmetrics.registerFontFamily("PTS", normal="PTS", bold="PTS-Bold", italic="PTS", boldItalic="PTS-Bold")
TZ = ZoneInfo("America/Sao_Paulo")


def fmt_datetime(value):
    if not value:
        return "Não informado"
    try:
        if isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(value / 1000, TZ)
        else:
            dt = datetime.fromisoformat(value)
        return dt.strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError, OSError):
        return "Não informado"


def gerar_pdf(record):
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("PTSBody", fontName="PTS", fontSize=9, leading=14, spaceAfter=5,
                              wordWrap="CJK"))
    styles.add(ParagraphStyle("PTSHeading", parent=styles["PTSBody"], fontName="PTS-Bold",
                              fontSize=11, spaceBefore=12, spaceAfter=8, keepWithNext=True))
    styles.add(ParagraphStyle("PTSTitle", parent=styles["PTSHeading"], fontSize=15, leading=20,
                              alignment=TA_CENTER))

    def p(value, style="PTSBody"):
        return Paragraph(escape(str(value or "Não informado")).replace("\n", "<br/>"), styles[style])

    story = [p("PERMISSÃO DE TRABALHO SEGURO", "PTSTitle"),
             p(f'{record["numero"]} • {CATS[record["categoria"]]["label"]}')]

    def field(label, value):
        # Blocos de parágrafos podem quebrar entre páginas, inclusive textos de 5.000 caracteres.
        story.append(Paragraph(f"<b>{escape(label)}:</b> {escape(str(value or 'Não informado')).replace(chr(10), '<br/>')}",
                               styles["PTSBody"]))

    field("Status", {"aberta": "Aberta", "encerrada": "Encerrada", "cancelada": "Cancelada"}.get(record["status"], record["status"]))
    field("Emissão", record.get("dataEmissao"))
    field("Local / Setor", record.get("local"))
    field("Empresa executante", record.get("empresa"))
    field("Validade", f'{fmt_datetime(record.get("validadeInicio"))} até {fmt_datetime(record.get("validadeFim"))}')
    field("Fuso horário", record.get("fuso", "America/Sao_Paulo"))
    field("Registrada por", record.get("criadaPor"))
    field("Recebida pelo servidor", fmt_datetime(record.get("createdAt")))
    story.append(p("Descrição do trabalho", "PTSHeading"))
    story.append(p(record.get("descricao")))
    story.append(p("Equipe executante", "PTSHeading"))
    story.append(p(record.get("equipe")))
    snapshot = record.get("checklistTextos") or {"risco": CHECKLISTS[record["categoria"]], "epi": EPI_COMUM}
    story.append(p("Checklist de segurança", "PTSHeading"))
    field("Versão", record.get("checklistVersao", "Legado — sem versão original"))
    for label, key, items in (("EPIs", "checklistEpi", snapshot["epi"]),
                              ("Específico da categoria", "checklistRisco", snapshot["risco"])):
        story.append(p(label, "PTSHeading"))
        for i, item in enumerate(items):
            checked = (record.get(key) or {}).get(str(i)) is True
            story.append(p(("[X] " if checked else "[ ] ") + item))

    def signature(label, sig):
        if not sig:
            story.append(p(label + ": sem evidência registrada"))
            return
        received = ("Não registrado no protótipo anterior" if sig.get("legado") else
                    fmt_datetime(sig.get("recebidaEm") or sig.get("dataHora")))
        block = [p(label, "PTSHeading"), p(sig.get("nome")), p("Recebida pelo servidor: " + received)]
        if sig.get("dataHoraDispositivo"):
            block.append(p("Horário informado pelo dispositivo: " + fmt_datetime(sig["dataHoraDispositivo"])))
        cells = []
        for key, width, height in (("foto", 28 * mm, 25 * mm), ("imagem", 65 * mm, 25 * mm)):
            value = sig.get(key)
            if value and value.startswith("data:image/"):
                raw = base64.b64decode(value.split(",", 1)[1])
                img = Image(io.BytesIO(raw))
                scale = min(width / img.imageWidth, height / img.imageHeight)
                img.drawWidth, img.drawHeight = img.imageWidth * scale, img.imageHeight * scale
                cells.append(img)
            else:
                cells.append(p("Sem imagem"))
        table = Table([cells], colWidths=[35 * mm, 105 * mm], hAlign="LEFT")
        table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                   ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#DBDFE3"))]))
        block.extend([table, Spacer(1, 5 * mm)])
        story.append(KeepTogether(block))

    story.append(p("Assinaturas e evidências fotográficas", "PTSHeading"))
    story.append(p("As fotografias são evidências visuais associadas às assinaturas. Não há reconhecimento biométrico automatizado."))
    for role, label in (("emitente", "Emitente / Técnico de Segurança"),
                         ("executante", "Executante Responsável"), ("supervisor", "Responsável pela Área")):
        signature(label, record.get("assinaturas", {}).get(role))
    if record.get("encerramento"):
        signature("Encerramento", record["encerramento"])
        field("Observações", record["encerramento"].get("observacoes"))
    if record.get("cancelamento"):
        story.append(p("Cancelamento", "PTSHeading"))
        field("Motivo", record["cancelamento"]["motivo"])
        field("Responsável", record["cancelamento"]["autor"])
        field("Data", fmt_datetime(record["cancelamento"]["dataHora"]))
    if record.get("legado"):
        story.append(p("Registro importado do protótipo anterior. Datas e evidências originais não foram verificadas retroativamente."))
    story.append(p("Assinaturas eletrônicas desenhadas em tela, sem certificação ICP-Brasil."))

    generated = fmt_datetime(int(datetime.now(TZ).timestamp() * 1000))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("PTS", 7)
        canvas.setFillColor(colors.HexColor("#626A75"))
        canvas.drawString(15 * mm, 13 * mm, f'{record["numero"]} • Gerado em {generated} (São Paulo)')
        canvas.drawRightString(A4[0] - 15 * mm, 13 * mm, f"Página {doc.page}")
        canvas.restoreState()

    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm,
                            topMargin=14 * mm, bottomMargin=22 * mm,
                            title=record["numero"], author="Aplicativo PTS")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
