# BH-S2-06 - Conhecimento, memoria, CRM, campanhas e conteudo

**Telas:** T35-T45  
**Depende de:** BH-S2-01, BH-S2-04  
**Estimativa:** 21 pontos

## Historia

Como equipe comercial e editorial, quero usar conhecimento confiavel, priorizar leads e produzir campanhas rastreáveis até a publicação.

## Escopo

- Biblioteca, documento, ingestao, chunks/erros, memoria operacional e busca/debug RAG.
- Contas, contatos, importacao, consentimento e deduplicacao assistida.
- Leads, sinais, score explicado, timeline e proxima acao.
- Pipeline/oportunidades, forecast, ganho/perda.
- Campanhas, estudio de conteudo, variantes, aprovação e calendário/publicacoes.

## Contratos backend

Knowledge ingestion/status/version/chunks/search; memory review/contest/expire; accounts/contacts/import/dedupe; leads/signals/scoring; opportunities/stages; campaigns/assets/publications. Definir upload, jobs, filtros de tenant, consentimento e erros de provider.

## Criterios de aceite

- [x] T35-T45 completas.
- [ ] Conteudo contestado deixa de aparecer em resultados mockados.
- [ ] Busca mostra fonte, score e filtros sem expor outro tenant.
- [x] Merge de duplicata exige preview e confirmacao.
- [ ] Mudanca de estagio exige campos configurados.
- [ ] Publicacao falha preserva payload e oferece acao segura.
- [ ] Handoff inclui schemas de importacao e lifecycle de jobs.

## Evidencia

Cobertura web T35-T45 e E2E ingestao -> busca, lead -> oportunidade e conteudo -> publicacao; teste unitario explicito exige preview antes da confirmacao do merge. Os demais criterios permanecem abertos.

## Fora de escopo

- Embeddings, enriquecimento, CRM e publicação reais.
