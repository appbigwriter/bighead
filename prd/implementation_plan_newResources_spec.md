# Especificacao Tecnica Fechada: Hermes Agent + AnythingLLM no BigHead

**Status:** Pronto para implementacao  
**Escopo:** backend, worker, contratos, observabilidade e testes  
**Fora de escopo:** qualquer alteracao visual de UI ou redesign de telas

## 1. Objetivo

Substituir o motor interno de execucao de agentes do BigHead por integracao com:

- Hermes Agent como motor de execucao e orquestracao cognitiva
- AnythingLLM como backend central de conhecimento e RAG

O BigHead permanece como camada de:

- governanca
- auditoria
- isolamento multi-tenant
- aprovacao humana
- custo e ROI por run
- rastreabilidade de execucao
- persistencia de estado de negocio

## 2. Decisao de arquitetura

### 2.1 Regra de ouro

O BigHead nao vai incorporar a logica interna do Hermes ou do AnythingLLM no codigo-fonte. A integracao deve ocorrer por adapters versionados, com contratos de entrada e saida explicitamente definidos.

### 2.2 Responsabilidades

#### BigHead

- criar e versionar agentes
- persistir politicas, limites e permissao
- criar e acompanhar runs
- calcular custo e ROI
- aplicar aprovacao humana
- guardar auditoria e evidencias
- ingerir documentos e encaminhar para RAG

#### Hermes

- executar o agente
- gerenciar skills e memoria de curto prazo
- decidir quando usar conhecimento externo
- produzir resposta final e metadados de uso

#### AnythingLLM

- indexar documentos
- fornecer workspace RAG
- responder consultas contextuais
- manter isolacao por workspace/tenant

## 3. Escopo fechado

### 3.1 Entra agora

- integracao Hermes via adapter
- sincronizacao de profiles de agente
- substituicao do executor atual de runs
- integracao AnythingLLM via adapter
- ingestao de documentos para workspace
- skill `query_knowledge_base`
- persistencia de metricas de run
- persistencia de status de ingestao
- logging estruturado
- testes unitarios, integracao e contrato
- atualizacao de configuracao e docs tecnicas

### 3.2 Nao entra

- nenhuma mudanca de interface visual
- nenhuma pagina nova
- nenhum redesenho de telas existentes
- nenhum recurso experimental sem contrato
- nenhuma dependencia de estado manual nao versionado

## 4. Contratos de integracao

### 4.1 Hermes

#### Entrada minima do adapter

O adapter deve enviar:

- `runId`
- `organizationId`
- `taskId`
- `workflowVersionId`
- `attempt`
- `policy`
- `agentId`
- `agentVersionId`
- `taskTitle`
- `taskObjective`
- `taskMetadata`
- `systemPrompt`
- `outputSchema`

#### Headers obrigatorios

- `Idempotency-Key`
- `X-Hermes-Profile`
- `X-BigHead-Run-Id`
- `X-BigHead-Organization-Id`

#### Saida minima esperada

O BigHead deve conseguir ler:

- identificador da execucao
- modelo usado
- tokens de entrada
- tokens de saida
- resposta final
- event id de provider
- erro, se houver

#### Regra

Se faltar `providerEventId`, `model`, `inputTokens` ou `outputTokens`, o run deve ser considerado falho.

### 4.2 AnythingLLM

#### Entrada minima do adapter

- arquivo do documento
- checksum
- mime type
- tamanho
- organizationId
- workspace
- artifactId

#### Operacoes obrigatorias

- upload de documento
- atualizacao de embeddings
- associacao ao workspace
- consulta por chat/query
- remocao/reprocessamento

#### Regra

Nao pode haver consulta cross-tenant. Todo documento precisa ser associado a um workspace explicito.

## 5. Estrutura de implementacao

### 5.1 API

#### Epic A: sincronizacao de agente com Hermes

Criar um servico de sincronizacao de profile que seja chamado sempre que:

- um agente for criado
- um agente for alterado
- um agente for desativado

Comportamento:

- gerar profile Hermes a partir do registro do agente
- persistir versao do profile
- registrar auditoria
- impedir publicacao inconsistente se o sync falhar

#### Epic B: integracao de ingestao com AnythingLLM

Criar um servico de ingestao de conhecimento que seja acionado quando:

- um artifact for aprovado para conhecimento
- um documento for marcado como base corporativa

Comportamento:

- validar checksum e ownership
- enviar arquivo ao AnythingLLM
- atualizar embeddings
- persistir status da operacao
- registrar eventual falha com dados para reprocesso

### 5.2 Worker

#### Epic C: substituir executor de LLM

O executor de runs deve ser substituido por um executor Hermes.

Regras:

- manter idempotencia
- manter policy de retry
- manter timeout
- manter calculo de custo
- manter validacao de schema de saida

#### Epic D: integracao de skill RAG

O worker deve permitir que o Hermes use a skill `query_knowledge_base`.

Regras:

- skill ativa somente quando o recurso estiver habilitado
- skill com workspace do tenant
- skill nunca consulta workspace alheio

## 6. Dados e versionamento

### 6.1 Profile Hermes

Cada profile deve conter:

- `agent_id`
- `organization_id`
- `agent_version_id`
- `name`
- `model`
- `system_prompt`
- `skills`
- `workspace`
- `risk_level`
- `enabled`
- `version`
- `created_at`
- `updated_at`

### 6.2 Status de ingestao

Cada documento enviado ao AnythingLLM deve guardar:

- `artifact_id`
- `organization_id`
- `workspace`
- `status`
- `checksum_sha256`
- `mime_type`
- `size_bytes`
- `external_document_id`
- `embeddings_updated_at`
- `error_code`
- `error_message`

### 6.3 Run telemetry

Cada run deve guardar:

- `run_id`
- `organization_id`
- `task_id`
- `agent_id`
- `agent_version_id`
- `hermes_profile`
- `provider_event_id`
- `provider_name`
- `model`
- `input_tokens`
- `output_tokens`
- `latency_ms`
- `queue_wait_ms`
- `rag_latency_ms`
- `amount`
- `currency`
- `status`
- `error_type`
- `error_message`
- `used_rag`
- `used_skill_query_knowledge_base`

## 7. Observabilidade e metricas

### 7.1 Latencia

Medir e armazenar separadamente:

- tempo de fila
- tempo de execucao Hermes
- tempo de consulta RAG
- tempo total do run

### 7.2 Custo por run

Registrar:

- custo de entrada
- custo de saida
- custo total
- moeda
- modelo

### 7.3 Taxa de falha

Classificar falhas em:

- falha de validacao
- falha de timeout
- falha de Hermes
- falha de AnythingLLM
- falha de politica
- falha de schema

### 7.4 Qualidade

Salvar sinalizacao de qualidade via:

- validacao automatica de schema
- aprovacao/revisao humana quando aplicavel

### 7.5 Manutencao

O custo de manutencao deve ser inferido por:

- numero de adapters
- numero de pontos de falha
- cobertura de testes
- volume de logs e incidentes

## 8. Regras de falha

### 8.1 Hermes indisponivel

- o run falha de forma controlada
- o erro e persistido
- retries seguem policy
- nao existe sucesso parcial silencioso

### 8.2 AnythingLLM indisponivel

Comportamento definido por policy:

- se RAG for obrigatorio, o run falha
- se RAG for opcional, o run pode prosseguir sem RAG e isso deve ser registrado explicitamente

### 8.3 Profile ausente ou invalido

- o agente nao deve ser publicado como ativo
- o run nao deve iniciar

## 9. Variaveis de ambiente

### 9.1 Hermes

- `HERMES_API_URL`
- `HERMES_API_KEY`
- `HERMES_PROFILES_DIR`
- `HERMES_DEFAULT_MODEL`
- `HERMES_TIMEOUT_SECONDS`

### 9.2 AnythingLLM

- `ANYTHING_LLM_API_URL`
- `ANYTHING_LLM_API_KEY`
- `ANYTHING_LLM_DEFAULT_WORKSPACE`
- `ANYTHING_LLM_TIMEOUT_SECONDS`

### 9.3 Flags de comportamento

- `LLM_PROVIDER_DEFAULT=hermes`
- `KNOWLEDGE_BACKEND=anythingllm`
- `KNOWLEDGE_BACKEND_REQUIRED=true`

## 10. Testes obrigatorios

### 10.1 Unitarios

#### HermesProfileSync

Cobrir:

- create
- update
- disable
- serializacao
- validacao de campos
- versionamento

#### HermesRunExecutor

Cobrir:

- montagem correta do payload
- headers obrigatorios
- valida do agente
- schema da saida
- parsing de usage
- calculo de custo
- erro quando faltar metadata obrigatoria

#### AnythingLlmClient

Cobrir:

- upload
- update embeddings
- query workspace
- erro de autenticacao
- erro de timeout
- erro de payload invalido

#### KnowledgeIngestionService

Cobrir:

- ingestao somente de documento aprovado
- persistencia de status
- associacao ao tenant correto
- idempotencia de reprocesso

### 10.2 Integracao

#### Criacao de agente

Validar:

- persistencia do agente
- sync Hermes
- versionamento
- auditoria
- bloqueio em caso de falha

#### Edicao de agente

Validar:

- nova versao de profile
- preservacao do historico
- agente ativo aponta para versao correta

#### Execucao de run

Validar:

- worker reclama job
- chama Hermes mockado
- registra tokens, custo e latencia
- finaliza com sucesso

#### Falha de Hermes

Validar:

- retry ou fail conforme policy
- persistencia do erro
- ausencia de sucesso falso

#### Ingestao de documento

Validar:

- upload para AnythingLLM
- update embeddings
- persistencia do vinculo
- status final correto

#### Falha de AnythingLLM

Validar:

- erro registrado
- reprocesso possivel
- documento nao marcado como indexado com sucesso

### 10.3 Contrato

#### Hermes

Validar:

- request minimo aceito
- response minimo interpretavel
- erro padronizado

#### AnythingLLM

Validar:

- upload
- embeddings
- query
- erros mapeados

## 11. Critérios de aceite finais

A integracao so e considerada pronta se:

- BigHead permanece como camada de governanca e auditoria
- Hermes executa os runs
- AnythingLLM armazena e serve conhecimento
- nao houve nenhuma mudanca visual
- agentes sao versionados
- runs medem custo, latencia e falha
- documentos sao ingeridos e consultaveis
- erros sao tratados de forma controlada
- testes passam
- contratos estao fixos e documentados

## 12. Ordem de implementacao recomendada

1. implementar cliente Hermes e profile sync
2. substituir executor atual do worker
3. implementar cliente AnythingLLM
4. implementar ingestao de documentos
5. registrar metrics e telemetry
6. adicionar testes unitarios
7. adicionar testes de integracao
8. adicionar testes de contrato
9. atualizar env e documentacao
10. executar validacao final end-to-end

## 13. Resultado esperado

Ao final desta entrega, o BigHead deve operar como plataforma de governanca e auditoria sobre um motor externo de execucao e uma base externa de conhecimento, com contratos versionados, medicao completa e nenhuma mudanca de interface visual.
