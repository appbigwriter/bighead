# BH-S3-06 - CRM, lead intelligence, campanhas, conteudo e experimentos

**Dominio:** Backend/Database/Integracao  
**Depende de:** BH-S3-02, BH-S3-03, BH-S3-04  
**Estimativa:** 34 pontos

## Historia

Como equipe comercial/editorial, quero conectar leads, oportunidades, conteúdo e testes para executar e aprender com resultado real.

## Escopo de dados

`crm_accounts`, `crm_contacts`, `leads`, `lead_signals`, `opportunities`, `campaigns`, `content_assets`, `experiments`, `experiment_variants`.

## Escopo funcional

- CRUD/importação/deduplicação de contas e contatos com consentimento/base legal.
- Enriquecimento provider-agnostic, sinais, ICP score versionado e próxima melhor ação explicada.
- Pipeline configurável, regras de estágio, forecast, ganho/perda.
- Campanhas, briefings, ativos, variantes, calendário e adapters de publicação.
- Aprovação obrigatória antes de ações externas conforme política.
- Experimentos com alocação, métrica primária, janela e stop rule; configuração imutável após start.
- Webhooks de CRM/publicação assinados e idempotentes.

## Criterios de aceite

- [x] APIs T39-T47 substituem mocks.
- [ ] Importação parcial gera relatório por linha e pode ser retomada.
- [x] Merge de duplicata preserva referências e auditoria.
- [x] Score exibe fatores e versão do algoritmo.
- [x] Estágio inválido não é persistido.
- [x] Publicação sem aprovação é bloqueada.
- [x] Experimento iniciado não aceita alteração de variantes/alocação/métrica.

## Casos de borda

Contato sem consentimento, webhook duplicado/fora de ordem, publicação parcial multicanal, timezone de calendário, oportunidade sem valor, soma de weights diferente de 1.

## Fora de escopo

- Atribuição agregada e dashboards, cobertos em BH-S3-07.
