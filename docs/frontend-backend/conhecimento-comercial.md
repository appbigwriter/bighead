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

## Schema de importacao CRM

`POST /v1/crm/imports` exige `Idempotency-Key` (ate 200 caracteres) e:

```json
{
  "source": "csv|xlsx|crm-provider",
  "consentBasis": "contract|legitimate_interest|consent",
  "rows": [
    {
      "externalId": "opcional",
      "recordType": "account|contact",
      "name": "obrigatorio",
      "email": "obrigatorio para contact",
      "company": "obrigatorio para contact sem accountExternalId",
      "accountExternalId": "opcional",
      "phone": "opcional",
      "ownerEmail": "opcional",
      "consentAt": "ISO-8601 quando consentBasis=consent",
      "customFields": {}
    }
  ]
}
```

Limites: `source` 1..120 caracteres, `consentBasis` 1..240, `rows` 1..1000. Campos
desconhecidos de cada linha ficam em `customFields`; o backend nao deve inferir consentimento.
A resposta `202` e `{ importId, dedupePreview[], validationSummary, replayed }`. O preview
identifica linha, candidato, score e acao `create|merge|reject`; merge so ocorre apos
confirmacao explicita. `422` retorna erros por `rowIndex` e `field`; `409` indica que a mesma
chave foi usada com payload diferente.

## Lifecycle de jobs

Ingestao de conhecimento e importacao CRM seguem
`queued -> running -> succeeded|partially_succeeded|failed|canceled`. Estados terminais nao
reabrem; retry cria nova tentativa vinculada ao mesmo `jobId` e conserva erros anteriores.
`POST /v1/knowledge/documents` tambem exige `Idempotency-Key` e devolve `202` com
`{ documentId, jobId, chunkPlan, replayed }`. A UI acompanha `knowledge.ingestion.updated`
ou `crm.import.updated`, usando polling com backoff quando Realtime estiver indisponivel.

Cada atualizacao contem `{ jobId, status, processed, total, errors[], updatedAt }`; erro tem
`{ code, message, rowIndex?|chunkIndex?, field?, retryable }`. `succeeded` libera o recurso;
`partially_succeeded` mostra itens rejeitados e exportacao do erro; `failed` preserva o
payload e so oferece retry quando `retryable=true`; `canceled` preserva auditoria. Eventos
duplicados sao deduplicados por `(jobId, status, updatedAt)` e eventos mais antigos nao
regredem o estado da UI.
