# Issues derivadas: Hermes Agent + AnythingLLM no BigHead

## Regras gerais

- Nao alterar UI.
- Nao deixar item funcional para depois.
- Cada issue precisa ter criterio de aceite binario.
- Cada issue precisa ter teste associado.

## Epic 1: Adapter Hermes

### Issue 1.1 - Criar cliente Hermes

**Escopo**
- implementar cliente HTTP para Hermes
- suportar chat/completions
- suportar headers obrigatorios
- suportar timeout e erro padronizado

**Aceite**
- request e response normalizados
- erro convertido para excecao interna consistente

**Testes**
- unitario com sucesso
- unitario com 500
- unitario com timeout
- unitario com header ausente

### Issue 1.2 - Sincronizar profile de agente

**Escopo**
- gerar profile Hermes a partir do agente BigHead
- persistir versao
- atualizar ao editar agente
- desativar ao despublicar/remover

**Aceite**
- todo create/update reflete no Hermes
- nenhuma versao antiga e perdida

**Testes**
- create profile
- update profile
- disable profile
- serializacao correta

### Issue 1.3 - Substituir executor de runs

**Escopo**
- trocar executor interno por HermesRunExecutor
- preservar idempotencia
- preservar calculo de custo
- preservar validacao de schema

**Aceite**
- run executa via Hermes
- custo e tokens persistem
- falha sem dados obrigatorios bloqueia execucao

**Testes**
- run feliz
- run com schema invalido
- run com resposta incompleta
- run com Hermes fora

## Epic 2: Adapter AnythingLLM

### Issue 2.1 - Criar cliente AnythingLLM

**Escopo**
- upload de documento
- associacao a workspace
- update embeddings
- query workspace
- remocao/reprocesso

**Aceite**
- chamada reconhece tenant/workspace
- erros ficam classificados

**Testes**
- upload ok
- embeddings ok
- query ok
- erro autenticacao
- erro timeout

### Issue 2.2 - Ingestao de conhecimento

**Escopo**
- acionar ingestao quando artefato for aprovado
- registrar status
- persistir vinculo artifact-documento
- suportar reprocesso idempotente

**Aceite**
- documento fica consultavel no workspace correto
- falha nao cria estado inconsistente

**Testes**
- ingestao feliz
- ingestao falha
- reprocesso
- tenant isolation

### Issue 2.3 - Skill de consulta RAG

**Escopo**
- registrar skill `query_knowledge_base`
- apontar para workspace do tenant
- ativar somente quando habilitada

**Aceite**
- Hermes consulta conhecimento somente quando apropriado
- nenhuma consulta cross-tenant

**Testes**
- skill habilitada
- skill desabilitada
- consulta com workspace correto
- consulta bloqueada para outro tenant

## Epic 3: Telemetria e auditoria

### Issue 3.1 - Persistir métricas de run

**Escopo**
- salvar latencia total
- salvar latencia de fila
- salvar latencia de RAG
- salvar tokens e custo
- salvar provider metadata

**Aceite**
- todo run concluido gera registro completo

**Testes**
- persistencia completa
- persistencia parcial bloqueada quando faltar dado obrigatorio

### Issue 3.2 - Classificacao de falhas

**Escopo**
- mapear erros de Hermes
- mapear erros de AnythingLLM
- mapear timeout
- mapear invalidacao de schema

**Aceite**
- cada falha tem tipo rastreavel

**Testes**
- cada classe de erro gera status correto

## Epic 4: Contratos e ambiente

### Issue 4.1 - Atualizar env

**Escopo**
- incluir variaveis Hermes
- incluir variaveis AnythingLLM
- documentar defaults e obrigatoriedade

**Aceite**
- app sobe com configuracao valida

**Testes**
- settings validas
- settings invalidas

### Issue 4.2 - Congelar contratos

**Escopo**
- documentar schemas de request/response
- documentar headers
- documentar campos persistidos

**Aceite**
- contrato passa a ser fonte de verdade para a implementacao

**Testes**
- contract tests para Hermes
- contract tests para AnythingLLM

## Epic 5: Integracao e validacao final

### Issue 5.1 - Smoke end-to-end de agente

**Escopo**
- criar agente
- sincronizar Hermes
- disparar run
- receber resposta
- persistir custo e auditoria

**Aceite**
- fluxo ponta a ponta passa sem UI change

**Testes**
- smoke e2e com Hermes mockado

### Issue 5.2 - Smoke end-to-end de conhecimento

**Escopo**
- subir documento
- indexar no AnythingLLM
- perguntar ao agente
- validar uso de RAG

**Aceite**
- resposta usa conhecimento indexado

**Testes**
- smoke e2e com AnythingLLM mockado

