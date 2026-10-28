"""Catálogo único dos checklists do protótipo; revisão técnica pendente."""
CHECKLIST_VERSION = "2026-10-v1"
CATS = {
    "altura": {"label": "Trabalho em Altura"},
    "confinado": {"label": "Espaço Confinado"},
    "eletricidade": {"label": "Eletricidade"},
    "quente": {"label": "Trabalho a Quente"},
}

CHECKLISTS = {
    "altura": [
        "Pontos de ancoragem inspecionados e aprovados",
        "Cinto de segurança tipo paraquedista em bom estado",
        "Talabarte duplo com absorvedor de energia",
        "Trava-quedas ou linha de vida instalado",
        "Área abaixo isolada e sinalizada",
        "Condições climáticas favoráveis (sem vento forte ou chuva)",
        "Capacete com jugular utilizado",
        "Análise de Risco (APR) revisada com a equipe",
    ],
    "confinado": [
        "Teste atmosférico realizado (O2, LEL, gases tóxicos)",
        "Ventilação forçada instalada e testada",
        "Vigia de entrada posicionado e treinado",
        "Plano de resgate definido e equipamento disponível",
        "Iluminação adequada (antichama, se necessário)",
        "Entrada isolada e sinalizada",
        "Comunicação estabelecida entre vigia e executante",
    ],
    "eletricidade": [
        "Desenergização confirmada",
        "Bloqueio e etiquetagem (LOTO) aplicados",
        "Teste de ausência de tensão realizado",
        "Aterramento temporário instalado, se aplicável",
        "EPIs dielétricos verificados (luvas, calçado)",
        "Ferramentas isoladas em bom estado",
        "Zona de risco isolada e sinalizada",
    ],
    "quente": [
        "Área isolada e sinalizada",
        "Materiais inflamáveis removidos ou protegidos (raio mín. 10m)",
        "Extintor de incêndio disponível no local",
        "Vigia contra incêndio designado",
        "Verificação pós-trabalho por 30 min após conclusão",
        "Ventilação adequada para fumos e gases",
    ],
}

EPI_COMUM = [
    "Capacete de segurança",
    "Óculos de proteção",
    "Luvas apropriadas ao risco",
    "Calçado de segurança",
    "Protetor auricular (quando aplicável)",
    "Uniforme / vestimenta adequada",
]

