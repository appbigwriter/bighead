# Frontend -> Backend Handoff

## Cobertura

Esta pasta consolida o handoff da Sprint 2 para a Sprint 3:

- `ENDPOINT-MATRIX.md`: matriz `T01-T56` com request, response, codigos HTTP, papel, cache/evento e erro critico.
- `openapi-snapshot.yaml`: snapshot versionado dos contratos prioritarios e schemas compartilhados usados pelo frontend.
- `acesso-organizacoes.md`: T01-T09.
- `colaboracao.md`: T10-T13.
- `tarefas-execucoes.md`: T14-T19.
- `governanca-automacao.md`: T20-T34.
- `conhecimento-comercial.md`: T35-T45.
- `analytics-administracao.md`: T46-T56.
- `TRANSICAO-MSW-API.md`: estrategia de substituicao gradual dos mocks.
- `RISCOS-RESIDUAIS-S2.md`: pendencias e riscos para Sprint 3.

## Garantias atuais

- `56/56` telas mapeadas na matriz.
- Snapshot OpenAPI versionado em [openapi-snapshot.yaml](/F:/Projetos/BigHead/docs/frontend-backend/openapi-snapshot.yaml).
- Componentes de tela consomem camada de servico/mock centralizada, sem importar fixtures diretamente.
- Jornadas E2E principais cobertas em desktop e mobile com auditoria Axe sem violacoes criticas/serias.
- Transporte assincrono permite trocar mock por HTTP sem mudancas nos componentes.
- Tenant, headers e cancelamento sao isolados por request, inclusive em SSR concorrente.
- Gates finais da Sprint 2: lint, typecheck, testes raiz, 141 testes web, build, guards e 20/20 execucoes E2E aprovados; revisao independente `PASS`.

## Proximo passo esperado

Conectar os dominios gradualmente ao backend real via feature flags, preservando os shapes, estados e codigos HTTP descritos nestes documentos.
