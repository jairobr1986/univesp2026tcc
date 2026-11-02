# Proteção de evidências e ciclo de vida dos dados

## Implementação

Fotos e assinaturas são criptografadas pela aplicação antes da gravação na tabela
`evidence`, usando AES-256-GCM, da biblioteca `cryptography`. Cada gravação gera
um nonce aleatório de 96 bits; a autenticação usa a etiqueta de 128 bits do GCM.
O envelope tem versão e associa criptograficamente o identificador da evidência,
a PTS e o tipo de mídia (AAD). Troca de vínculo, adulteração e chave incorreta
impedem a leitura. Nenhuma chave é armazenada no banco junto às evidências.

A descriptografia ocorre em memória nas rotas protegidas e na geração de PDF.
A importação de registros legados também criptografa as imagens. Imagens antigas
sem envelope não são servidas: a API retorna indisponibilidade até a migração.
Os demais campos da PTS (nomes, equipe, contatos, JSON e histórico) não recebem
criptografia por campo nesta implementação. Permanecem sujeitos ao controle de
acesso, transporte seguro e à política de retenção. Não há reconhecimento facial.

Referência técnica: [AESGCM na documentação oficial](https://cryptography.io/en/latest/hazmat/primitives/aead/#cryptography.hazmat.primitives.ciphers.aead.AESGCM).

## Ativação local e na Vercel

No ambiente virtual:

```powershell
python -m pip install -r requirements.txt
python manage.py crypto-key
```

`crypto-key` cria `EVIDENCE_KEY` no `.env` e preserva uma chave existente válida.
Não imprime a chave. Ela é independente de `SECRET_KEY`, tem 32 bytes aleatórios
em base64 e não pode ser uma senha escolhida pelo usuário.

Antes de publicar o código novo, copie **somente o valor** de `EVIDENCE_KEY`, sem
aspas externas, para a variável secreta de mesmo nome na Vercel (Production).
Preserve uma cópia em cofre privado, separada do banco, com acesso restrito ao
responsável. Perder a chave impede recuperar as imagens. Não substitua a chave
para redefinir usuários ou sessões. Rotação requer migração específica com a
chave antiga e a nova; não está automatizada nesta versão.

Para os registros já existentes, faça backup privado e opere em janela de
manutenção, sem emissões/importações/descarte concorrentes. Configure localmente
`DATABASE_URL` para **o banco que deseja migrar** (PostgreSQL/Neon de produção
ou SQLite local) e a mesma chave que será utilizada na Vercel. Não publique a URL.

```powershell
python manage.py encrypt-evidence
python manage.py encrypt-evidence --apply
python manage.py encrypt-evidence
```

O primeiro comando simula; o segundo criptografa em transação; o terceiro deve
indicar zero imagens a criptografar. Registros já criptografados são autenticados,
o que torna a migração repetível e detecta chave incorreta. Falhas desfazem a
transação. Migração em volume grande exige dimensionamento/janela apropriada.

Depois, faça deploy/redeploy e confira login, emissão, foto, PDF e encerramento
com dados fictícios. A aplicação recusa inicialização sem chave válida.
O ajuste no repositório não atualiza variáveis nem migra o Neon automaticamente.
Backups feitos antes da migração continuam com imagens sem esta proteção.

## Política de retenção e descarte

**Responsável:** administrador designado pelo grupo, com validação do responsável
pelos registros de segurança do trabalho. Antes de usar dados reais, documentar
finalidade, fundamento do tratamento, prazo aplicável, responsáveis e exceções.
Não se presume um prazo legal único para todas as PTS nem autorização de uso
real apenas pela implementação desta camada.

**Prazo:** `RETENTION_DAYS`, inteiro positivo, aprovado e registrado pelo
responsável. Não há valor padrão nem tarefa automática de exclusão. Para a
apresentação acadêmica, usar pessoas/dados fictícios e eliminar os registros
de demonstração ao fim da finalidade acadêmica, conforme prazo aprovado pelo
grupo. Os números utilizados nos testes são cenários fictícios, não prazo legal.

**Marco inicial:** última atualização persistida da PTS encerrada ou cancelada.
Permissões abertas não são eliminadas por esse comando, mesmo que vencidas;
o administrador deve revisar e encerrar/cancelar as que perderam a finalidade.
Revisar também permissões abertas abandonadas para evitar conservação indefinida.

**Exceções:** antes de cada descarte, verificar obrigações de conservação,
auditorias e litígios. Para impedir a exclusão de uma PTS específica:

```powershell
python manage.py retention-hold IDENTIFICADOR_DA_PTS
# Somente depois de cessar a justificativa de conservação:
python manage.py retention-release IDENTIFICADOR_DA_PTS
```

Registrar justificativa, autorização e revisão do bloqueio em controle
administrativo restrito. O bloqueio não recebe justificativa jurídica automática.

**Execução:** com `RETENTION_DAYS` configurada no ambiente de manutenção, simular,
conferir a quantidade, avaliar as exceções e só então aplicar:

```powershell
python manage.py purge-expired
python manage.py purge-expired --apply
```

O descarte remove integralmente PTS elegíveis, imagens, assinaturas, nomes,
contatos e eventos relacionados em transação, preservando apenas contadores de
numeração. É uma operação administrativa restrita ao terminal, não uma rota
pública. É irreversível no banco ativo e não deve ser executada sem revisão.
Guardar comprovante administrativo com data, operador, prazo, autorização e
quantidade, sem copiar fotografias ou dados pessoais desnecessários. Recomenda-se
revisão mensal; não há agendamento embutido nesta versão.

**Backups e cópias:** exclusão SQL é descarte lógico do banco ativo, não garantia
de sobrescrita física de páginas, WAL, réplicas, snapshots ou backups do provedor.
O responsável deve registrar a janela real de recuperação/retenção do Neon e
de outros backups e garantir sua expiração, acesso restrito e eliminação das
cópias locais. Uma restauração deve reaplicar os descartes antes de reabrir o
acesso. PDFs baixados/compartilhados incluem dados e imagens descriptografados;
seus destinatários e operadores precisam observar a mesma finalidade e política.
A aplicação não consegue revogar anexos externos já enviados.

O compartilhamento manual por WhatsApp/e-mail pode incluir um link assinado do
PDF, gerado por administrador ou operador autenticado mediante CSRF. O link
expira em 15 minutos e é invalidado por alterações no estado da PTS. A geração
é registrada sem armazenar o token no evento. O portador do link acessa o PDF
sem login; isso é informado antes da geração. Mensagens e aplicativos externos
podem conservar o link e baixar o documento durante a validade. A expiração não
revoga cópias já baixadas. Não há comprovação de entrega ou identidade de quem
baixou. A proteção `no-store` também se aplica ao download por link.

## Limites e fundamento

As medidas apoiam necessidade, segurança e prevenção (art. 6º), eliminação e
hipóteses de conservação (arts. 15–16) e medidas de proteção (art. 46) da
[LGPD, texto atualizado](https://www2.camara.leg.br/legin/fed/lei/2018/lei-13709-14-agosto-2018-787077-normaatualizada-pl.html).
A escolha de AES-256-GCM é técnica; não é uma imposição específica da LGPD.
A associação de fotografia à assinatura não executa comparação biométrica.
Criptografia não substitui definição da base legal, informação aos titulares,
gestão de acessos, resposta a incidentes e governança, nem certifica conformidade
integral. Comprometimento simultâneo da aplicação e da chave continua sendo risco.

## Verificação

`tests/test_privacy.py` cobre adulteração, chave incorreta, vínculo AAD,
aleatoriedade do nonce, bytes protegidos no banco, migração repetível e rollback,
consulta/PDF e descarte com simulação, prazo e bloqueio de conservação.
Os testes utilizam banco temporário e dados fictícios; não demonstram a ativação
da proteção no ambiente de produção.
