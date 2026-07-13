# Transicao MSW -> API real

## Objetivo

Trocar a camada mockada da Sprint 2 por backend real na Sprint 3 sem reescrever componentes visuais nem alterar a semantica dos estados tratados pelo frontend.

## Regras

- Nenhum componente de tela deve importar fixtures diretamente.
- Dados entram pela camada `lib/workspace-service.ts` durante a Sprint 2 e passam para cliente HTTP tipado na Sprint 3.
- Responses reais devem preservar naming, enums, codigos HTTP e estados descritos em `ENDPOINT-MATRIX.md`.
- O snapshot `openapi-snapshot.yaml` eh a referencia inicial para gerar tipos e validar payloads prioritarios.

## Estrategia

1. Substituir a implementacao mockada da camada de servico por cliente HTTP tipado, mantendo a mesma assinatura consumida pelos componentes.
2. Manter adaptacoes de borda em mappers e nunca dentro das telas.
3. Introduzir feature flags por dominio:
   - `frontend_api_access`
   - `frontend_api_collaboration`
   - `frontend_api_tasks`
   - `frontend_api_governance`
   - `frontend_api_automation`
   - `frontend_api_knowledge`
   - `frontend_api_commercial`
   - `frontend_api_analytics_admin`
4. Virar dominio por dominio usando estes passos:
   - `mock-service -> typed client`
   - `typed client -> contract test`
   - `contract test -> feature flag parcial`
   - `feature flag parcial -> dominio totalmente real`

## Validacoes antes de virar real

- Contract tests verdes entre OpenAPI, tipos TS e payload backend.
- Estados `loading`, `empty`, `403`, `409`, `410`, `422` e `500` exercitados por dominio.
- Paginacao por cursor coberta nos modulos que listam colecoes.
- Eventos de invalidação e freshness alinhados com o comportamento visual ja implementado.
- Zero import de fixture fora da camada de mocks/servicos.
