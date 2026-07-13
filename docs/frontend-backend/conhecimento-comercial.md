# Conhecimento e comercial

## Escopo

Cobertura de `T35-T45`: biblioteca de conhecimento, ingestao, memoria, busca semantica, contas, contatos, leads, oportunidades, campanhas, conteudo e publicacoes.

## Contratos necessarios

| Bloco | Endpoint | Regra chave |
|---|---|---|
| Conhecimento | `GET /v1/knowledge/documents` | lista por tenant com status de ingestao |
| Ingestao | `POST /v1/knowledge/documents` | job assinc com status por chunk |
| Memoria | `GET /v1/memory/items`, `POST /v1/memory/items/{id}/contest` | contestacao remove item dos resultados mockados |
| Busca | `POST /v1/search/semantic` | score, fonte e filtro de confidencialidade |
| CRM base | `GET /v1/crm/accounts`, `GET /v1/crm/contacts`, `POST /v1/crm/imports` | importacao com preview de dedupe |
| Leads | `GET /v1/crm/leads`, `GET /v1/crm/leads/{leadId}` | score explicado e timeline |
| Oportunidades | `POST /v1/crm/opportunities/{id}/stage` | exige campos por etapa |
| Campanhas | `GET /v1/content/campaigns` | status e objetivo claros |
| Conteudo | `GET/POST /v1/content/assets` | variantes, aprovacoes e versoes |
| Publicacoes | `GET /v1/content/publications`, `POST /v1/content/publications/{id}/retry` | payload preservado em falha |

## Erros obrigatorios

- `409` merge de duplicata em conflito
- `422` importacao ou stage change invalida
- `424` provider de publicacao indisponivel
- `500` parse de documento falhou
