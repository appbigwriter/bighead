# Frontend -> Backend Handoff

## Cobertura

Esta pasta consolida o handoff da Sprint 2 para a Sprint 3:

- `ENDPOINT-MATRIX.md`: matriz `T01-T56` com request, response, codigos HTTP, papel, cache/evento e erro critico.
- `openapi-snapshot.yaml`: espelho publicado do contrato canonico em
  `packages/contracts/openapi/openapi.yaml`, cobrindo a matriz e as rotas FastAPI implementadas.
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
- OpenAPI 3.1 canonico cobre todas as operacoes `T01-T56`; modelos de rotas ja implementadas
  sao extraidos do FastAPI e os demais permanecem placeholders explicitos da matriz.
- O teste `apps/api/tests/test_openapi_contract.py` bloqueia drift entre matriz, FastAPI,
  contrato canonico e snapshot, valida referencias e `operationId` duplicado.
- `uv run --project apps/api python scripts/sync_openapi.py` sincroniza os dois artefatos;
  `pnpm --filter @bighead/contracts generate` regenera os tipos TypeScript.
- Componentes de tela consomem camada de servico/mock centralizada, sem importar fixtures diretamente.
- Jornadas E2E principais cobertas em desktop e mobile com auditoria Axe sem violacoes criticas/serias.
- Transporte assincrono permite trocar mock por HTTP sem mudancas nos componentes.
- Tenant, headers e cancelamento sao isolados por request, inclusive em SSR concorrente.
- Gates finais da Sprint 2: lint, typecheck, testes raiz, 141 testes web, build, guards e 20/20 execucoes E2E aprovados; revisao independente `PASS`.

## Proximo passo esperado

Conectar os dominios gradualmente ao backend real via feature flags, preservando os shapes, estados e codigos HTTP descritos nestes documentos.
