# PTS · Permissão de Trabalho Seguro

Protótipo acadêmico da UNIVESP: aplicação web responsiva em **Flask**, com
assinatura desenhada em tela, fotografia associada, checklists por categoria,
PDF e histórico. Pode ser instalado como PWA no celular.

**Hospedagem prevista:** Vercel Hobby + PostgreSQL Neon no plano gratuito,
respeitando as cotas dos serviços. O projeto está preparado para publicação;
criar as contas, fornecer as variáveis e executar o deploy continuam necessários.

## Primeiro acesso: qual é o usuário e a senha?

**Não existe usuário nem senha padrão.** Você escolhe os dois ao executar a
configuração inicial. Digitar um nome na tela de login não cria uma conta.

O login foi acrescentado para restringir o acesso às PTS, fotografias e
assinaturas e identificar a conta responsável por emitir, encerrar ou cancelar
uma permissão. O nome do signatário é preenchido durante a assinatura e não
substitui a conta de acesso ao aplicativo.

Se aparecer **“O acesso ainda não foi configurado”** e o botão **Entrar** estiver
desabilitado, nenhum acesso foi carregado pelo servidor. Na execução local,
faça o seguinte no terminal do VS Code, aberto na pasta `pts-backend`:

1. Pare o servidor com **Ctrl+C** no terminal em que ele está rodando.
2. Execute:

   ```powershell
   .\.venv\Scripts\python manage.py setup
   ```

3. Responda às perguntas no terminal:

   | Pergunta | O que preencher |
   |---|---|
   | Usuário | Um nome que você escolher, por exemplo `jairo` |
   | Nome para exibição | Seu nome, por exemplo `Jairo` |
   | Perfil | `admin` para o primeiro responsável pelo projeto; Enter também seleciona `admin` |
   | Senha | Uma senha escolhida por você, com 10 a 256 caracteres |
   | Repita a senha | Digite a mesma senha novamente |

   **A senha não aparece enquanto você digita no terminal, nem como asteriscos.**
   Isso é esperado: digite normalmente e pressione Enter. O usuário aceita de
   3 a 60 letras minúsculas, números, ponto, hífen ou sublinhado. A senha não pode
   começar ou terminar com espaços.

4. Aguarde a mensagem **“Acesso salvo no .env”** e inicie novamente:

   ```powershell
   .\.venv\Scripts\python app.py --port 5001
   ```

5. Abra **http://localhost:5001/**, atualize a página e entre com o usuário e a
   senha que você acabou de escolher.

O comando cria o arquivo **`.env`** automaticamente; não é necessário editar o
JSON de usuários manualmente. **`.env.example` é somente um modelo**: preencher
esse arquivo não configura o aplicativo. O login do app também é independente
das credenciais de Vercel, Neon, banco de dados, e-mail ou Twilio.

### Adicionar usuários ou redefinir uma senha

Execute `manage.py setup` novamente. Informe um usuário novo para adicionar uma
conta ou o mesmo usuário existente para substituir sua senha, nome e perfil.
Depois reinicie o servidor. A senha original não pode ser consultada no `.env`,
pois ele armazena apenas um hash.

Na Vercel, a configuração é feita pelas variáveis **`APP_USERS`** e
**`SECRET_KEY`** no painel, seguida de **Redeploy**. Executar o setup local não
atualiza automaticamente a publicação. Consulte a seção de deploy abaixo.

## Executar no Windows

Requer Python 3.12 ou superior. Os comandos abaixo são para PowerShell, na pasta
`pts-backend`. Não é necessário ativar o ambiente virtual.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python manage.py setup
.\.venv\Scripts\python app.py --port 5001
```

Abra **http://localhost:5001/**. O comando `setup` pede usuário, nome, perfil e
senha (mínimo 10 caracteres); grava apenas o hash da senha e uma chave de sessão
no `.env`. Repita-o para adicionar outros usuários. Reinicie o servidor após
alterar os acessos. Nunca envie o `.env` ao GitHub ou o publique.

Não use Live Server para iniciar a aplicação. Sem `DATABASE_URL`, a execução local
usa **`pts-v2.db`**, separado do `pts.db` original. O servidor local inicializa o
novo esquema automaticamente. Para `flask run`/WSGI, execute antes:

```powershell
.\.venv\Scripts\python manage.py init-db
```

No macOS/Linux substitua `.\.venv\Scripts\python` por `.venv/bin/python`.

## Acessos e responsabilidades

| Perfil | Consultar PTS, evidências, PDF e histórico | Emitir / encerrar / envio opcional | Cancelar |
|---|---|---|---|
| `consulta` | Sim | Não | Não |
| `operador` | Sim | Sim | Não |
| `admin` | Sim | Sim | Sim |

Os usuários pertencem à mesma equipe e podem consultar seus registros. Este
protótipo não implementa separação entre empresas/organizações. Os três
signatários são identificados nominalmente no dispositivo do operador; cada
assinatura não exige uma conta independente. A conta que registra a operação é
gravada no histórico. Mudar o hash da senha invalida as sessões desse usuário.

As sessões duram até 8 horas, usam cookies HttpOnly/SameSite Strict e proteção
CSRF. Há limite de oito tentativas de login por usuário a cada 15 minutos,
armazenado no banco compartilhado. Na Vercel o cookie também exige HTTPS.

## Fluxo do protótipo

1. Entre e escolha **Nova PTS**.
2. Escolha a categoria e preencha empresa, local, atividade, equipe e validade.
3. A emissão deve ser na data atual de São Paulo; a validade começa nessa data
   e o fim deve ser posterior ao início.
4. Confirme cada item do checklist e dos EPIs.
5. Fotografe e colete as três assinaturas: emitente, executante e responsável
   pela área. Um toque isolado não é aceito como assinatura.
6. Emita. O servidor valida os dados, atribui número único e registra o evento.
7. Baixe ou compartilhe o PDF. Para encerrar, registre nova assinatura e foto.

Modificar dados ou checklists antes da emissão descarta as assinaturas já
coletadas. O número não é calculado no celular. Repetir a mesma requisição de
emissão usa uma chave de idempotência para evitar registros duplicados.

Permissões abertas com validade vencida são sinalizadas na interface. Não há
renovação automática. O encerramento só ocorre uma vez e não pode ser
sobrescrito. O cancelamento exige perfil admin e motivo; preserva dados,
evidências e histórico. Exclusão permanente não é oferecida pela API.

### Celular, câmera e PWA

- Use a URL **HTTPS** publicada. Um endereço `http://192.168...` pode abrir a tela
  mas não liberar a câmera. `localhost` funciona no computador.
- Autorize o acesso à câmera e confira o rosto capturado antes de assinar.
- No Android, use a opção de instalação do navegador. No iPhone, use Safari →
  Compartilhar → Adicionar à Tela de Início. A interface de instalação varia.
- A PWA armazena no cache somente arquivos públicos. APIs, fotos e PDFs usam
  `no-store` e não são colocados no cache do service worker.
- **Emissão e encerramento precisam de internet.** Offline, há uma tela de
  orientação. Não existe sincronização de permissões offline.
- Rascunhos ficam no `sessionStorage` da aba, por usuário, sem fotos, assinaturas,
  senha ou token. Podem conter nomes da equipe e dados do trabalho. São
  descartados ao sair; é possível retomar ou descartar na lista. Não são backup
  e podem ser perdidos ao fechar a aba ou pelo gerenciamento do navegador.
- Após uma falha de envio do formulário, os dados continuam na tela. Se uma
  emissão foi aceita mas a resposta não chegou, tente novamente sem editar os
  dados. Se houver conflito, consulte a lista antes de criar outra permissão.

### Compartilhamento gratuito

O padrão é **manual**, sem necessidade de Twilio ou SMTP:

- **Compartilhar PDF** prepara o arquivo; quando o navegador suporta arquivos
  pela Web Share API, aparece **PDF pronto — escolher aplicativo**.
- Se o recurso não estiver disponível, o PDF é baixado para anexação manual.
- Os contatos cadastrados permitem abrir e-mail/WhatsApp com mensagem pronta.
  Esses links **não anexam o arquivo**: baixe o PDF e anexe-o antes de enviar.
- O aplicativo não afirma que uma mensagem manual foi enviada ou entregue.

O envio automático antigo foi mantido como recurso opcional. Para usá-lo,
instale as dependências, configure SMTP/Twilio no `.env.example` e defina
`ENABLE_AUTO_SEND=1`. O WhatsApp precisa de `PUBLIC_BASE_URL` HTTPS pública e
de uma configuração válida do provedor. O link de download assinado expira em
15 minutos e é invalidado se o registro for atualizado. Quem possuir esse link
poderá baixar aquele PDF durante a validade; as demais rotas continuam privadas.
O histórico diferencia solicitação, falha e aceitação pelo provedor. **Aceitação
não comprova entrega.** Há intervalo mínimo de um minuto entre solicitações por
PTS. Não há retentativas automáticas nem webhook de entrega nesta versão.

## Publicar na Vercel com Neon

1. Coloque o código em um repositório GitHub privado ou público, sem `.env`,
   bancos, backups ou arquivos de testes. Esta cópia local inicialmente não
   contém um repositório Git; não há envio automático ao GitHub.
2. Importe o repositório na Vercel. Se a pasta fizer parte de um repositório
   maior, selecione `pts-backend` como **Root Directory**.
3. Use o preset **Flask**. O arquivo `vercel.json` já o declara; `app.py` expõe
   `app`. A versão Python fica em `.python-version` (3.14, usada nos testes locais).
4. No Marketplace/Storage, adicione **Neon** e selecione o plano gratuito
   disponível. Conecte-o ao projeto.
5. Configure as variáveis de ambiente de Production (e Preview, se necessário):

   | Variável | Valor |
   |---|---|
   | `DATABASE_URL` | URL PostgreSQL **pooled** do Neon, preservando `sslmode=require` |
   | `SECRET_KEY` | Valor da chave gerada pelo `manage.py setup`, ou outra chave aleatória forte |
   | `APP_USERS` | Objeto JSON com usuários, perfis e hashes gerado pelo setup |
   | `ENABLE_AUTO_SEND` | `0` para o compartilhamento manual |

   O Marketplace pode criar outras variáveis; confirme que existe
   **`DATABASE_URL`**. Copie os valores do `.env` para os campos da Vercel
   **sem as aspas externas** do arquivo dotenv. Não copie a senha original para
   `APP_USERS`: use o `password_hash` gerado. Não exponha variáveis no frontend.
6. Antes de abrir o aplicativo publicado, inicialize o banco uma vez. Na sua
   máquina, coloque temporariamente a URL do Neon no `.env` e execute:

   ```powershell
   .\.venv\Scripts\python manage.py init-db
   ```

   Esse comando cria o esquema no banco indicado por `DATABASE_URL`. Não apaga
   tabelas existentes. Não rode migrações como efeito do import de `app.py`.
7. Faça Deploy/Redeploy. Verifique `/api/health`, entre e teste uma emissão.
8. No celular, abra a URL HTTPS, autorize a câmera e valide assinatura, PDF e
   compartilhamento. Use apenas dados fictícios durante a apresentação.

O `.vercelignore` exclui segredos, bancos locais, backups e testes. Arquivos em
`public/` são servidos pelo CDN da Vercel; somente o HTML inicial usa templates
do Flask. O Neon guarda
os dados persistentes; a aplicação **recusa SQLite quando `VERCEL` está definido**.
SQLAlchemy usa conexões curtas e `NullPool`, adequadas à URL pooled do Neon.
Importar `app.py` não faz conexão nem cria tabelas no banco remoto.

Planos e limites podem mudar. Configure apenas os planos gratuitos necessários,
acompanhe consumo e teste o projeto antes da defesa. A preparação local não
comprova que um deploy remoto foi realizado ou que as credenciais estão válidas.

Referências: [Flask na Vercel](https://vercel.com/docs/frameworks/backend/flask),
[PostgreSQL no Marketplace](https://vercel.com/docs/postgres),
[Neon na Vercel](https://vercel.com/marketplace/neon),
[SQLite na Vercel](https://vercel.com/kb/guide/is-sqlite-supported-in-vercel).

## Banco antigo, migração e backup

O arquivo `pts.db` original não é alterado. Para consultar seus registros na nova
aplicação, faça backup e importe explicitamente no banco de destino configurado:

```powershell
.\.venv\Scripts\python manage.py import-legacy pts.db
```

A importação é transacional e evita repetir registros da mesma origem. Copia as
evidências para a tabela privada, marca os registros como **legados**, registra
o evento e informa que os textos originais do checklist não foram versionados.
Datas antigas não são convertidas em horários comprovados do servidor. Números
duplicados recebem sufixo de legado. Arquivos de imagem inválidos interrompem e
desfazem a importação; o banco de origem permanece intacto. Não renomeie/mova a
origem entre importações repetidas, pois o caminho faz parte da identificação.

Para backup do SQLite local, escolha um arquivo que ainda não exista:

```powershell
.\.venv\Scripts\python manage.py backup-sqlite backups/pts-2026-10-27.db
```

Para restaurar SQLite: pare o servidor, preserve o banco atual com outro nome,
copie um backup íntegro para o caminho configurado e reinicie. Valide listagem,
PDF e evidências. Nunca restaure por cima de uma aplicação em execução.

Para PostgreSQL, use as ferramentas PostgreSQL com `DATABASE_URL` exportada no
terminal (sem exibir a senha). Guarde os backups fora do repositório:

```powershell
pg_dump --dbname=$env:DATABASE_URL --format=custom --file=pts-backup.dump
```

Restaure em **um banco novo e vazio**, nunca no banco em uso:

```powershell
pg_restore --dbname=$env:RESTORE_DATABASE_URL --no-owner --no-acl pts-backup.dump
```

Confira os registros restaurados e só depois aponte a aplicação para a nova URL.
Os comandos `pg_dump`/`pg_restore` exigem instalação separada. Os backups contêm
dados pessoais e imagens: proteja-os e mantenha uma política de descarte.

O esquema inicial é versão 1 (`schema_versions`). Futuras alterações de colunas
exigem migrações explícitas e backup; `create_all` não altera tabelas existentes.

## Estrutura

```text
app.py                 API, sessões, perfis, histórico e documentos privados
database.py            esquema, transações e sequência PostgreSQL/SQLite
validation.py          regras de emissão e validação/compactação de imagens
catalog.py             fonte única de categorias e checklists
pdf_generator.py       PDF multipágina, fontes Unicode e equipe executante
sender.py              SMTP/Twilio opcionais
manage.py              setup, inicialização, importação e backup SQLite
templates/index.html   estrutura acessível da interface, servida pelo Flask
public/static/app.js   interface móvel e compartilhamento manual
public/static/app.css  estilos responsivos
public/sw.js           cache somente de arquivos públicos
tests/                 regressões da API, PDF, importação e navegador
```

Os dados centrais ficam em `permits`; imagens compactadas em `evidence`; eventos
em `audit_events`; sequências em `permit_sequences`; tentativas de login em
`login_attempts`. Para este volume acadêmico, as evidências binárias ficam no
PostgreSQL privado, dispensando outro provedor. Para uma operação maior, migrar
essas imagens para armazenamento de objetos privado é uma evolução recomendada.

Listagens são paginadas e filtradas no servidor e não transportam fotos nem
assinaturas. O detalhe usa URLs autenticadas. Cada emissão salva uma cópia dos
textos e da versão do checklist, preservando sua interpretação em PDFs futuros.
Imagens têm limites de bytes/dimensões, são decodificadas e regravadas em JPEG,
sem metadados EXIF; a requisição inteira é limitada a 3,5 MB.

## Testes

```powershell
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest -q
```

Os testes usam bancos e pessoas fictícias. Cobre emissão das quatro categorias,
erros de validação, imagens inválidas, autorização/CSRF, idempotência, concorrência,
histórico, cancelamento, PDF longo, paginação, importação e fluxo móvel com câmera
simulada. Testes de envio usam provedores simulados: não enviam mensagens reais.

Os testes de navegador usam Chrome/Edge local no Windows. Em outro ambiente,
instale Chromium com `python -m playwright install chromium`, ou defina
`CHROME_PATH` com o executável. Para executar somente a API:

```powershell
.\.venv\Scripts\python -m pytest tests/test_api.py tests/test_maintenance.py -q
```

O caminho `.pytest-tmp` é reservado aos testes e recriado pelo pytest; nunca guarde
arquivos próprios nele. Capturas de tela dos testes ficam nessa pasta e são
excluídas do Git/deploy. Testes em navegador simulado não substituem o teste em
Android/iPhone reais nem uma avaliação de usabilidade com participantes.

## Delimitação e alinhamento com o TCC

- Fotografia associada à assinatura é **evidência visual**, sem comparação facial,
  detecção de prova de vida ou garantia automática de identidade.
- Assinatura desenhada em tela não usa certificado ICP-Brasil. O histórico registra
  operações da aplicação, mas não é um registro criptograficamente inviolável.
- Perfis de acesso existem; signatários não são autenticados individualmente.
- Compartilhamento é manual por padrão; envio pelo servidor é opcional e depende
  de credenciais e regras dos provedores.
- Não existe integração com eSocial nem certificação de conformidade normativa.
  Os checklists precisam ser revisados pelo profissional responsável para cada
  contexto de trabalho; este software é um protótipo acadêmico.
- Métricas de tempo, melhoria operacional e SUS devem vir de medições e avaliações
  efetivamente realizadas. Não foram produzidas automaticamente por estes ajustes.

O relatório acadêmico não está nesta pasta. Sua redação deve refletir estes
limites, a persistência implementada e os resultados reais dos testes.
