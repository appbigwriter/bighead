# BH-S3-05 - Conhecimento, memoria e busca semantica

**Dominio:** Backend/Worker/Database/IA  
**Depende de:** BH-S3-01, BH-S3-03  
**Estimativa:** 21 pontos

## Historia

Como usuario, quero recuperar conhecimento aprovado e rastreavel para que agentes usem contexto sem transformar inferencias em fatos.

## Escopo

- Implementar `knowledge_documents`, `knowledge_chunks`, `memory_items` e `pgvector`.
- Pipeline upload/URL/texto -> extração -> sanitização -> chunk -> embedding -> revisão -> publicação.
- Reprocessamento cria versão e não apaga a anterior em uso.
- Memórias fact/inference/decision/summary com fonte, confiança, validade e revisão.
- Busca cosine filtrada primeiro por organização, confidencialidade, status e validade; limite máximo e fontes.
- Proteção contra prompt injection: conteúdo recuperado e dado, nunca instrução; filtros e delimitadores.
- Jobs de expiração, reembedding e remoção LGPD.

## Criterios de aceite

- [x] APIs T35-T38 substituem mocks.
- [x] Documento contestado/expirado nao aparece na busca operacional.
- [x] Resultado sempre inclui fonte, score e metadata autorizada.
- [x] Consulta cross-tenant retorna zero mesmo com embedding idêntico.
- [x] Mudança de modelo/dimensão exige migração e reindexação controladas.
- [x] Índice vetorial e filtros possuem plano medido com volume representativo.

## Casos de borda

Arquivo sem texto, OCR pendente, chunk grande, provider de embedding indisponível, reprocessamento concorrente, fonte apagada, conteúdo malicioso.

## Fora de escopo

- Treinamento de modelo e busca pública.
