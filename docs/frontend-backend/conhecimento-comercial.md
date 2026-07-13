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
| CRM base | `POST /v1/crm/imports`, `POST /v1/crm/imports/{importId}/resume`, `POST /v1/crm/accounts/{accountId}/merge` | relatorio por linha, retomada e merge auditavel |
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
      "accountName": "obrigatorio",
      "domain": "opcional",
      "contactName": "obrigatorio quando email estiver presente",
      "email": "opcional",
      "phone": "opcional",
      "ownerId": "opcional; deve ser membro ativo",
      "consentStatus": "unknown|granted|denied|revoked",
      "legalBasis": "opcional; usa consentBasis como fallback",
      "createLead": true,
      "icpScore": 80,
      "scoreFactors": {"fit": {"weight": 0.6, "contribution": 48}},
      "scoreAlgorithmVersion": "icp-v2.1"
    }
  ]
}
```

Limites: `source` 1..120 caracteres, `consentBasis` 1..240, `rows` 1..1000. O backend
nao infere consentimento. Quando `icpScore` estiver presente, fatores nao vazios e
`scoreAlgorithmVersion` sao obrigatorios. A resposta `202` inclui
`{ importId, dedupePreview[], rowReports[], validationSummary, status, replayed }`. Cada linha
fica persistida como `accepted|failed`, com payload, tentativa, IDs criados e erro. `409`
indica que a mesma chave foi usada com payload diferente.

## Retomada e merge

`POST /v1/crm/imports/{importId}/resume` aceita somente linhas atualmente `failed`, preserva o
numero original da linha, incrementa `attempts` uma vez e recalcula o agregado como
`partial|completed` na mesma transacao. Repetir o mesmo payload retorna replay sem incrementar
tentativas; payload divergente concorrente recebe `409`.

`POST /v1/crm/accounts/{accountId}/merge` recebe `{ targetAccountId, reason }`. A transacao move
contatos, leads e oportunidades, mantem a origem como tombstone (`merged_into_id`, `merged_at`) e
acrescenta um evento imutavel `crm.account.merged` ao audit log.

## Lifecycle de jobs

Ingestao de conhecimento segue `queued -> running -> succeeded|partially_succeeded|failed|canceled`.
`POST /v1/knowledge/documents` tambem exige `Idempotency-Key` e devolve `202` com
`{ documentId, jobId, chunkPlan, replayed }`. A UI acompanha `knowledge.ingestion.updated`,
usando polling com backoff quando Realtime estiver indisponivel.

Cada atualizacao contem `{ jobId, status, processed, total, errors[], updatedAt }`; erro tem
`{ code, message, rowIndex?|chunkIndex?, field?, retryable }`. `succeeded` libera o recurso;
`rowIndex` identifica a linha original de importacao e `chunkIndex` identifica o trecho do
documento, quando aplicavel.
`partially_succeeded` mostra itens rejeitados e exportacao do erro; `failed` preserva o
payload e so oferece retry quando `retryable=true`; `canceled` preserva auditoria. Eventos
duplicados sao deduplicados por `(jobId, status, updatedAt)` e eventos mais antigos nao
regredem o estado da UI.
