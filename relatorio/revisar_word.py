"""Atualiza somente a redação de 5.1–5.7; conserva as demais partes do DOCX."""
from pathlib import Path
import copy
import hashlib
import re
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
SOURCE = next(Path('C:/Users/jairo/Downloads').glob('TCC*18-10-26.docx'))
TARGET = ROOT / 'TCC_revisado_5.1_a_5.7_criptografia.docx'
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

SECTIONS = {
'5.1': [
'O sistema foi desenvolvido como uma aplicação web responsiva, com arquitetura cliente-servidor. A interface utiliza HTML, CSS e JavaScript e se comunica com a API do servidor por requisições HTTP com dados em JSON. A assinatura desenhada e a fotografia são capturadas no navegador, enquanto a validação, a persistência e a geração dos documentos são executadas no servidor Python com Flask.',
'A camada de persistência utiliza SQLAlchemy para acesso ao banco de dados. Na execução local, o sistema utiliza SQLite quando não há uma conexão externa configurada. Para publicação na Vercel, o código exige PostgreSQL persistente, com configuração de conexão por DATABASE_URL, permitindo a utilização do serviço Neon. Dessa forma, os registros e as evidências não dependem do armazenamento temporário da execução da aplicação.',
'O código-fonte está versionado no GitHub, em https://github.com/jairobr1986/univesp2026tcc. O repositório reúne os módulos do servidor, os arquivos da interface, a configuração de publicação e os testes automatizados. O versionamento permite acompanhar alterações e manter uma referência compartilhada da implementação.',
'A aplicação foi publicada na Vercel e seu endereço de acesso é https://univesp2026tcc.vercel.app/. A configuração do projeto identifica o framework Flask e estabelece cabeçalhos para os arquivos públicos. O acesso por HTTPS permite utilizar a câmera do dispositivo nos navegadores compatíveis, mediante autorização do usuário.',
'As responsabilidades foram divididas entre app.py, para rotas e controle de acesso; validation.py, para validação dos dados e imagens; database.py, para persistência e transações; catalog.py, para categorias e checklists; pdf_generator.py, para geração de PDF; e sender.py, para integrações opcionais de envio. A interface permanece separada em templates/index.html e nos arquivos públicos de JavaScript e CSS.',
'As principais bibliotecas empregadas são Flask, SQLAlchemy, psycopg, ReportLab, Pillow e python-dotenv. A implementação privilegia regras no servidor e geração centralizada do PDF, reduzindo a dependência de verificações executadas exclusivamente no dispositivo do usuário.'
],
'5.2': [
'A modelagem implementada combina tabelas relacionais para identificação, relacionamento e controle das operações com um campo textual em JSON para o conteúdo completo da PTS. O esquema é definido no módulo database.py e utilizado tanto com SQLite quanto com PostgreSQL.',
'A tabela permits concentra o identificador da permissão, número único, categoria, status, local, empresa, conta responsável e datas de criação e atualização. Também armazena o identificador da requisição, o resumo criptográfico do conteúdo recebido e o registro completo da permissão em JSON. Os estados implementados são aberta, encerrada e cancelada.',
'A tabela evidence armazena as imagens de assinaturas e fotografias como conteúdo binário, acompanhadas de identificador, tipo de mídia e chave estrangeira para permits. Cada permissão pode possuir várias evidências; seus identificadores são referenciados no conteúdo da PTS. A consulta às imagens ocorre por rotas protegidas da API.',
'A tabela audit_events mantém o histórico de eventos de cada permissão, com identificação da conta que realizou a operação, ação, instante e detalhes. A tabela permit_sequences controla a numeração por categoria e ano; login_attempts registra tentativas de autenticação; e schema_versions identifica a versão inicial do esquema.',
'As contas de acesso são carregadas da configuração APP_USERS, com hash de senha e perfil de autorização, e não de uma tabela de usuários. Os perfis são admin, operador e consulta. Esses perfis de acesso são distintos dos papéis de emitente, executante e responsável pela área que constam nas assinaturas da PTS.',
'As categorias e os textos dos checklists são definidos no catálogo do código, e não em tabelas específicas. No momento da emissão, a aplicação grava a versão e uma cópia dos textos utilizados no registro da permissão, preservando o conteúdo histórico mesmo que o catálogo seja alterado posteriormente.'
],
'5.3': [
'As regras de negócio são verificadas no servidor antes da gravação de uma PTS. A função permit, no módulo validation.py, verifica a categoria, os campos obrigatórios, os limites dos textos, os checklists de EPIs e de riscos, as três assinaturas com fotografia e os contatos opcionais. Os itens dos checklists devem corresponder aos itens esperados e estar explicitamente confirmados.',
'A emissão deve corresponder à data atual no fuso America/Sao_Paulo. O início da validade deve ocorrer nessa data, e o término deve ser posterior ao início. O servidor registra o instante de recebimento das assinaturas, mantendo separadamente o horário informado pelo dispositivo, quando fornecido e aceito pela validação.',
'O processamento das imagens verifica formato, tamanho, dimensões e possibilidade de decodificação. A assinatura também passa por uma verificação de conteúdo visual mínimo, destinada a rejeitar imagens vazias ou insuficientes. As imagens aceitas são normalizadas antes do armazenamento. Essa verificação não identifica o autor da assinatura nem reconhece o rosto fotografado.',
'A numeração é atribuída exclusivamente pelo servidor, no formato PTS-CATEGORIA-ANO-SEQUÊNCIA. A função next_number utiliza uma sequência por categoria e ano, atualizada por operação de inserção ou atualização com retorno do valor. A gravação da permissão, das evidências e do evento de emissão ocorre em uma transação, e o número possui restrição de unicidade no banco.',
'Para tratar repetições de envio, a emissão exige a chave Idempotency-Key, associada à conta autenticada. O servidor compara o resumo criptográfico dos dados com o de uma requisição previamente processada: quando chave e conteúdo coincidem, retorna a permissão existente; quando o conteúdo diverge, informa conflito. Esse mecanismo evita duplicações decorrentes da repetição da mesma solicitação.',
'O encerramento exige nova assinatura com fotografia e somente é aceito para uma PTS aberta. O cancelamento também se aplica apenas a permissões abertas, requer perfil admin e motivo, e preserva os registros anteriores. A API não oferece exclusão permanente de permissões. Emissões, encerramentos e cancelamentos são registrados no histórico com a conta responsável.',
'O acesso à API utiliza autenticação por sessão, perfis de autorização e proteção contra requisições forjadas por meio de token CSRF. As senhas são verificadas por hash, e o sistema limita tentativas de login. A conta autenticada identifica quem registrou a operação; os signatários são informados nominalmente durante a coleta, sem exigência de uma conta independente para cada assinatura.'
],
'5.4': [
'O PDF é gerado no servidor pelo módulo pdf_generator.py, com a biblioteca ReportLab, a partir do registro persistido e de suas evidências. O documento apresenta número, categoria, status, empresa, local, descrição do trabalho, equipe, validade, versão e itens do checklist, assinaturas, fotografias e dados de encerramento ou cancelamento, quando existentes. A composição admite múltiplas páginas e utiliza rodapé com identificação da PTS, data de geração e paginação.',
'A geração utiliza a cópia dos textos dos checklists armazenada na emissão, preservando a correspondência entre o documento e o registro histórico. O PDF informa que as assinaturas são desenhadas em tela, sem certificação ICP-Brasil, e que as fotografias são evidências visuais sem reconhecimento biométrico automatizado.',
'O fluxo padrão de distribuição é manual: o usuário pode baixar o PDF ou utilizar o compartilhamento de arquivos do navegador, quando disponível, escolhendo o aplicativo e o destinatário. A interface também pode abrir e-mail ou WhatsApp com mensagem preenchida. A abertura desses aplicativos não comprova o envio nem garante que o PDF tenha sido anexado; quando necessário, o usuário deve anexar o arquivo manualmente.',
'O código também contém integrações opcionais de envio pelo servidor, habilitadas por ENABLE_AUTO_SEND e pelas credenciais dos provedores. O e-mail utiliza SMTP com anexo, e o WhatsApp utiliza Twilio com acesso temporário ao PDF por link assinado. Esses recursos dependem de configuração específica e não devem ser considerados ativos apenas porque a aplicação está publicada.'
],
'5.5': [
'A interface foi organizada para uso em dispositivos móveis, com formulário dividido em categoria de risco, dados gerais, checklists, assinaturas e contatos opcionais. Após autenticar-se, o usuário pode consultar permissões com busca, filtros e paginação. A disponibilidade de ações considera o perfil da conta, e a autorização é novamente verificada no servidor.',
'O fluxo de emissão começa pela escolha da categoria e pelo preenchimento de empresa, local, atividade, equipe e validade. Em seguida, o usuário confirma os itens dos checklists e coleta as assinaturas com fotografia do emitente, do executante e do responsável pela área. Alterações nos dados ou checklists após a coleta descartam as assinaturas da interface e exigem nova coleta. O número da PTS é atribuído somente após o processamento da emissão pelo servidor.',
'Uma permissão nasce com status aberta e pode ser encerrada mediante nova assinatura com fotografia ou cancelada por um administrador mediante justificativa. A tela de detalhes apresenta o documento, as evidências e o histórico. Permissões abertas com validade vencida recebem um aviso na interface, sem renovação automática da validade.',
'A aplicação possui manifesto e service worker para utilização como Progressive Web App (PWA), conforme o suporte do navegador. O cache se restringe a arquivos públicos; os registros, as fotografias e os PDFs não são armazenados nesse cache. A emissão e o encerramento dependem de conexão com o servidor. Há uma página de orientação para acesso sem internet, sem sincronização de permissões offline.',
'O preenchimento pode ser preservado temporariamente como rascunho no sessionStorage da aba, vinculado ao usuário, sem fotografias e assinaturas. Ao retomar, o usuário deve conferir os dados e coletar novamente as evidências. Esse recurso auxilia a continuidade do preenchimento, mas não representa cópia de segurança dos registros.'
],
'5.6': [
'A assinatura é desenhada em um elemento canvas por eventos de ponteiro, permitindo interação por toque, caneta ou mouse. A interface exige um traçado mínimo antes da confirmação. A fotografia é obtida por getUserMedia, com solicitação da câmera frontal e autorização do navegador. O quadro capturado é convertido em imagem JPEG e apresentado para conferência antes de ser associado à assinatura.',
'O formulário reúne nome, imagem da assinatura, fotografia e horário informado pelo dispositivo. O servidor valida os dados e as imagens, registra seu instante de recebimento e armazena as evidências vinculadas à PTS. O encerramento utiliza uma nova coleta de assinatura e fotografia, sem substituir as evidências da emissão.',
'A expressão validação facial, neste protótipo, refere-se ao registro de uma fotografia associada à assinatura para possível conferência humana posterior. Não há comparação biométrica com imagem de referência, identificação automática de pessoas, detecção de rosto ou verificação de vivacidade. A presença de uma fotografia não comprova, por si só, a identidade do signatário.',
'O uso da câmera requer contexto seguro, como o endereço HTTPS da aplicação publicada, e permissão do usuário. O acesso às evidências exige autenticação, e os arquivos não integram o cache público da PWA. A adoção futura de reconhecimento facial automatizado exigirá uma avaliação específica de requisitos técnicos e de proteção de dados.'
],
'5.7': [
'O código da versão desenvolvida está disponível em https://github.com/jairobr1986/univesp2026tcc, e o endereço de acesso à aplicação publicada é https://univesp2026tcc.vercel.app/. A reprodução local deve utilizar as instruções do README correspondente à versão consultada, pois a configuração de execução local é distinta da configuração de publicação.',
'Na raiz do projeto, app.py implementa a API e a integração dos módulos; database.py define o esquema e as operações de persistência; validation.py concentra validações; e catalog.py mantém as categorias e os checklists. Os módulos pdf_generator.py e sender.py tratam, respectivamente, dos documentos e das integrações opcionais de envio.',
'A interface está organizada em templates/index.html, public/static/app.js e public/static/app.css. Os arquivos public/static/manifest.webmanifest e public/sw.js fornecem os recursos da PWA. As dependências de execução constam em requirements.txt, as de desenvolvimento em requirements-dev.txt, e a configuração de publicação em vercel.json.',
'No Windows, a preparação local pode ser feita com os comandos python -m venv .venv e .\\.venv\\Scripts\\python -m pip install -r requirements.txt. Em seguida, .\\.venv\\Scripts\\python manage.py setup configura a conta inicial e a chave de sessão; a execução é iniciada com .\\.venv\\Scripts\\python app.py --port 5001. Na ausência de DATABASE_URL, utiliza-se o arquivo local pts-v2.db. O arquivo .env contém configuração privada e não deve ser incluído no repositório.',
'Para a publicação, a aplicação exige DATABASE_URL para PostgreSQL, SECRET_KEY e APP_USERS no ambiente da Vercel. O comando python manage.py init-db inicializa o esquema no banco configurado. O código utiliza conexões curtas com NullPool, compatíveis com a conexão agrupada do Neon. As credenciais e a disponibilidade dos serviços devem ser verificadas no ambiente de publicação.',
'A pasta tests contém testes da API, de manutenção e do navegador. Após instalar requirements-dev.txt, a execução pode ser solicitada com python -m pytest -q no ambiente virtual. A presença desses testes permite reproduzir verificações, mas não constitui, isoladamente, evidência de aprovação de todos os cenários. Não são apresentados nesta seção novos resultados de desempenho nem validação de uso em campo.'
]
}

SECTIONS['5.2'].append('Na versão atual, o conteúdo binário das fotos e assinaturas é criptografado pela aplicação antes da gravação na tabela evidence, utilizando AES-256-GCM por meio da biblioteca cryptography. O envelope armazena sua versão, um nonce aleatório de 96 bits e o conteúdo autenticado. O identificador da evidência, o vínculo com a PTS e o tipo de mídia compõem os dados associados autenticados. A chave de 256 bits é configurada fora do banco, em EVIDENCE_KEY, e não integra o repositório.')
SECTIONS['5.3'].append('O ciclo de vida dos dados possui comandos administrativos de retenção e descarte. O prazo RETENTION_DAYS deve ser aprovado pelo responsável e não tem valor padrão. A contagem considera a última atualização da PTS encerrada ou cancelada; permissões abertas e registros com bloqueio de conservação são excluídos da seleção. O comando purge-expired apenas simula por padrão e exige --apply para remover, em transação, a permissão e suas evidências e eventos. O procedimento requer revisão das obrigações de conservação, registro administrativo da execução e tratamento das cópias e backups. Não há descarte agendado automaticamente.')
SECTIONS['5.4'].append('Para a geração do PDF, as imagens são descriptografadas em memória após a autorização de acesso. Evidências antigas sem migração, adulteradas ou incompatíveis com a chave são recusadas. O PDF exportado contém as imagens legíveis e fica fora da proteção criptográfica por campo do banco; por isso, o compartilhamento e a conservação dos arquivos exportados também devem observar a política de privacidade.')
SECTIONS['5.6'].append('A criptografia autenticada acrescenta confidencialidade e detecção de alterações às fotografias e assinaturas persistidas. A biblioteca gera um nonce novo para cada gravação, e a chave é mantida como segredo da implantação. Essas medidas apoiam os princípios de necessidade, segurança e prevenção e as medidas de proteção previstas na LGPD, sem constituir, isoladamente, certificação de conformidade. A captura fotográfica permanece uma evidência visual, sem comparação biométrica automatizada.')
SECTIONS['5.7'].append('A proteção das evidências está implementada em evidence_crypto.py, e os procedimentos administrativos em privacy_maintenance.py. O comando python manage.py crypto-key gera a chave no .env sem imprimi-la. Antes da publicação, a mesma chave deve ser configurada na Vercel. O comando encrypt-evidence simula a migração das imagens antigas e, com --apply, aplica a criptografia em transação. A migração verifica evidências já protegidas e pode ser repetida. Sua execução no banco de produção é uma etapa operacional específica; a alteração do código não comprova que ela tenha sido realizada.')
SECTIONS['5.7'].append('O documento PRIVACIDADE.md descreve a gestão da chave, migração, critérios de retenção, bloqueios de conservação e descarte. A exclusão do banco ativo é lógica e não comprova sobrescrita física de páginas ou remoção imediata de backups, snapshots, réplicas e PDFs externos. A janela de retenção dessas cópias deve ser registrada e acompanhada pelo responsável. Os testes automatizados adicionais utilizam dados fictícios e verificam criptografia, integridade, migração, consulta e descarte; não representam validação do ambiente de produção. A fundamentação utiliza a Lei nº 13.709/2018, especialmente arts. 6º, 15, 16 e 46, e a documentação oficial AESGCM da biblioteca cryptography (https://cryptography.io/en/latest/hazmat/primitives/aead/).')

def text_of(raw):
    root = ET.fromstring(b'<root xmlns:w="' + NS['w'].encode() + b'">' + re.sub(rb'<w:(drawing|pict)\b.*?</w:\1>', b'', raw, flags=re.S) + b'</root>')
    return ''.join(n.text or '' for n in root.findall('.//w:t', NS))

def plain_text(raw):
    return ''.join(ET.fromstring(b'<t>' + s + b'</t>').text or '' for s in re.findall(rb'<w:t(?:\s[^>]*)?>(.*?)</w:t>', raw, re.S))

with ZipFile(SOURCE) as src:
    original = src.read('word/document.xml')
    paragraphs = list(re.finditer(rb'<w:p(?:\s[^>]*)?>.*?</w:p>', original, re.S))
    edits = []
    for key, texts in SECTIONS.items():
        start = next(i for i,m in enumerate(paragraphs) if plain_text(m.group()).startswith(key+' '))
        following = '5.' + str(int(key[-1])+1)
        end = next(i for i in range(start+1,len(paragraphs)) if plain_text(paragraphs[i].group()).startswith(following+' '))
        candidates = [m for m in paragraphs[start+1:end] if plain_text(m.group()).strip() and not plain_text(m.group()).startswith('Figura') and b'<w:drawing' not in m.group() and b'<w:pict' not in m.group()]
        template = candidates[0].group()
        ppr = re.search(rb'<w:pPr\b.*?</w:pPr>', template, re.S)
        rpr = re.search(rb'<w:rPr\b.*?</w:rPr>', template, re.S)
        def paragraph(t):
            return b'<w:p>'+(ppr.group() if ppr else b'')+b'<w:r>'+(rpr.group() if rpr else b'')+b'<w:t xml:space="preserve">'+escape(t).encode('utf-8')+b'</w:t></w:r></w:p>'
        # Mantém figuras e legendas na posição relativa dos parágrafos originais.
        for i,m in enumerate(candidates):
            replacement = paragraph(texts[i]) if i < len(texts) else b''
            if i == len(candidates)-1:
                replacement += b''.join(paragraph(t) for t in texts[len(candidates):])
            edits.append((m.start(),m.end(),replacement))
    updated = original
    for a,b,replacement in sorted(edits,reverse=True):
        updated = updated[:a]+replacement+updated[b:]
    ET.fromstring(updated)
    # Comprova preservação literal antes de 5.1 e a partir de 5.8.
    before = next(m.start() for m in paragraphs if plain_text(m.group()).startswith('5.1 '))
    after = next(m.start() for m in paragraphs if plain_text(m.group()).startswith('5.8 '))
    assert updated[:before] == original[:before]
    assert updated.endswith(original[after:])
    with ZipFile(TARGET,'w') as out:
        for item in src.infolist():
            out.writestr(item,updated if item.filename=='word/document.xml' else src.read(item.filename))

with ZipFile(SOURCE) as a, ZipFile(TARGET) as b:
    assert a.namelist()==b.namelist()
    assert all(a.read(n)==b.read(n) for n in a.namelist() if n!='word/document.xml')
    assert len(re.findall(rb'<w:drawing\b',original))==len(re.findall(rb'<w:drawing\b',updated))
print(TARGET)
print('Verificado: somente redação de 5.1 a 5.7 alterada; 5.8 e demais partes preservadas.')
