# Sprint 3 - gates operacionais locais

Os procedimentos para ambientes remotos estão em
[`docs/runbooks`](runbooks/README.md). A existência dos runbooks não comprova
provisionamento, deploy, alertas, backup gerenciado ou go-live.

## Restore reproduzivel

`pnpm db:restore-test` cria um dump logico dos schemas `auth`, `storage`,
`private` e `public`, restaura em um banco temporario isolado e compara a
integridade por hash e contagem de todas as tabelas nesses quatro schemas. O
gate tambem compara RLS, policies, grants, funcoes, triggers e indices. O banco
temporario e o dump sao removidos mesmo quando o teste falha. Nomes de bancos
de sistema e o banco de origem sao recusados. O gate usa o RTO do MVP
(`8 h`) como limite superior.

O teste e deliberadamente local: ele prova que migrations, extensoes e dados
podem ser recuperados, mas nao prova largura de banda, tamanho ou operacao do
backup gerenciado de staging. Para go-live, repetir sobre um backup de staging,
registrar inicio/fim, validar os blobs do Storage (o gate local cobre apenas os
metadados em `storage`) e medir o RPO
contra o ultimo evento confirmado. Meta: RPO <= 24 h e RTO <= 8 h.

## Performance reproduzivel

`pnpm db:performance-test` cria 5.000 linhas transacionais em cada workload,
confirma que elas sao visiveis sob RLS como membro do tenant Atlas, executa 750
leituras e calcula p95 para salas, tarefas e notificacoes. Os dados de carga sao
revertidos ao final. Cada operacao deve ficar abaixo de 500 ms, conforme RNF-02.

Esse gate isola o banco local e detecta regressao de query/RLS. O aceite de
producao continua exigindo carga ponta a ponta em staging, incluindo API,
pooler, rede e volume representativo, alem de disponibilidade mensal de 99,5%.

## Sequencia de verificacao

1. `pnpm db:verify`
2. `pnpm db:performance-test`
3. `pnpm db:restore-test`
4. testes de API/worker e contratos
5. E2E sem MSW contra a stack local
6. repetir restore e carga em staging antes do go-live

Nenhum destes comandos acessa ou altera um projeto Supabase remoto.

## Handoff operacional

- [Readiness local/staging/produção](runbooks/READINESS-CHECKLIST.md)
- [Staging e produção](runbooks/STAGING-PRODUCTION.md)
- [Release, rollback e forward-fix](runbooks/RELEASE-ROLLBACK-FORWARD-FIX.md)
- [Incidentes](runbooks/INCIDENT-RESPONSE.md)
- [Backup e restore](runbooks/BACKUP-RESTORE.md)
- [Observabilidade e SLOs](runbooks/OBSERVABILITY-SLOS.md)
- [Providers externos](runbooks/EXTERNAL-APIS-HANDOFF.md)

## Ultima evidencia local

Em 2026-07-14, o restore terminou em 47,96 s com hashes de dados e catalogo
equivalentes para 55 tabelas publicas e quatro schemas protegidos. O teste de
performance mediu p95 de 3,158 ms para busca vetorial, 103,735 ms para
notificacoes, 107,055 ms para salas e 115,436 ms para tarefas, abaixo do
orcamento de 500 ms. O E2E real sem MSW passou 20/20 em desktop/mobile com Axe.
Esses gates locais nao medem RPO, blobs, rede, pooler ou disponibilidade remota.
