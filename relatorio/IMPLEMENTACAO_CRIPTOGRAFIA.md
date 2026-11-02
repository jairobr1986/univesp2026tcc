# Registro técnico — 02/11/2026

Implementados AES-256-GCM para fotos e assinaturas, autenticação do vínculo da
evidência com a permissão, chave externa obrigatória, migração transacional,
bloqueio administrativo de conservação e descarte com simulação por padrão.
Detalhes, fundamentos e procedimentos: [PRIVACIDADE.md](../PRIVACIDADE.md).

## Execução neste ambiente

- Biblioteca `cryptography` instalada no ambiente virtual.
- Chave `EVIDENCE_KEY` criada no `.env` privado, preservando contas existentes.
- Banco SQLite local: backup em `backups/antes-criptografia-20261102.db`.
- Migração: 12 evidências criptografadas; conferência seguinte: zero pendentes e
  12 autenticadas. Nenhuma PTS foi descartada.
- Suíte completa de API, manutenção, privacidade e navegador: 57 testes passaram.
- Após acrescentar quatro casos de chave ausente/inválida, os oito testes de
  privacidade passaram. Dados dos testes são fictícios, em banco temporário.
- `.env`, bancos, backups e pastas temporárias excluídos do Git; relatório e
  pastas temporárias também excluídos do pacote de publicação.
- Word gerado: `TCC_revisado_5.1_a_5.7_criptografia.docx`. O script verifica
  preservação literal do XML anterior a 5.1 e a partir de 5.8, assim como dos
  demais arquivos internos do documento, incluindo imagens. Não foi realizada
  inspeção visual no Microsoft Word; conferir paginação, sumário e figuras.

## Etapas restantes no ambiente de produção

O Neon e a implantação Vercel não foram alterados nesta execução. Antes do
deploy da nova versão, configurar a chave privada `EVIDENCE_KEY` em Production,
preservar uma cópia segura e migrar o banco Neon com essa mesma chave, conforme
o procedimento documentado. Conferir os fluxos no endereço publicado depois.

O prazo `RETENTION_DAYS` depende de aprovação e registro pelo responsável.
Não foi escolhido um prazo legal arbitrário nem programado descarte automático.
O backup anterior à migração contém as imagens anteriores e requer proteção,
controle de acesso e expiração conforme a política.
