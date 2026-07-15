Perfeito. Vou ser direto e rigoroso: **não mexer na interface visual**, **não deixar nada para depois** e **definir a integração de forma fechada para o modelo de implementação seguir sem ambiguidade**.

Abaixo está a especificação minuciosa da mudança, organizada para virar guia de execução.

---

# Especificação de Integração

## Objetivo
Substituir o motor interno de execução de agentes do BigHead por uma integração com:

- **Hermes** como motor de execução e orquestração cognitiva
- **AnythingLLM** como backend central de conhecimento/RAG

Enquanto isso, o **BigHead permanece responsável por**:

- governança
- auditoria
- RLS/isolamento
- aprovação humana
- custo/ROI por run
- rastreabilidade
- persistência de estado de negócio
- controle de ciclo de vida dos agentes

---

# Princípios de Escopo

## O que entra agora
Tudo abaixo entra na primeira implementação:

- adapter do Hermes
- integração com AnythingLLM
- sincronização de agentes
- ingestão de documentos
- consulta RAG via skill
- registro de métricas
- logging estruturado
- fallback seguro
- testes unitários
- testes de integração
- testes de contrato
- atualização de variáveis de ambiente
- documentação técnica de operação

## O que não entra
- nenhuma mudança de UI
- nenhum redesign
- nenhuma alteração visual de telas já definidas
- nenhuma funcionalidade “para depois”
- nenhuma migração parcial com coexistência indefinida entre motores
- nenhum experimento manual fora dos contratos definidos

---

# Arquitetura Final Desejada

## Responsabilidades por componente

### BigHead
Continua dono de:
- cadastro de agente
- edição de agente
- policy e governança
- orçamento e risco
- fila e execução dos runs
- auditoria e custos
- aprovação humana
- ingestão de documentos corporativos
- gestão de tenant e permissões
- persistência de evidências

### Hermes
Passa a ser responsável por:
- execução do agente
- uso de skills nativas
- memória de curto prazo
- tool use interno
- decisão de quando consultar conhecimento
- resposta final ao prompt
- uso do modelo definido pelo perfil

### AnythingLLM
Passa a ser responsável por:
- indexação de documentos
- workspace de conhecimento
- busca semântica
- resposta contextual de RAG
- isolamento do conteúdo por workspace

---

# Integração Hermes

## Estratégia
O BigHead não vai “copiar” o Hermes para dentro do código.  
Ele vai falar com o Hermes por **adapter explícito**, usando HTTP e contratos fixos.

## O que será criado

### 1. `HermesClient`
Um cliente de integração na API ou em um pacote compartilhado para:

- enviar perfil do agente
- consultar status quando necessário
- chamar chat/completions
- capturar tokens, modelo e metadata
- normalizar resposta em estrutura interna do BigHead

### 2. `HermesProfileSync`
Serviço responsável por:

- criar profile no Hermes ao criar agente no BigHead
- atualizar profile ao editar agente
- desativar/remover profile ao remover agente
- versionar profile com base em `agent_id` e `agent_version_id`

### 3. `HermesRunExecutor`
Substitui o executor atual interno de LLM nos runs.

Ele deve:
- receber `RunJob`
- validar se o run tem agente publicado, habilitado e com prompt válido
- montar payload compatível com o Hermes
- chamar `POST /v1/chat/completions`
- enviar cabeçalho de idempotência
- enviar referência do profile
- interpretar resposta
- normalizar uso de tokens
- devolver `ProviderResult`

---

# Contrato Hermes

## Entrada esperada
O adapter deve enviar:

- `runId`
- `organizationId`
- `taskId`
- `workflowVersionId`
- `attempt`
- `policy`
- `agentId`
- `agentVersionId`
- `systemPrompt`
- `outputSchema`
- `taskTitle`
- `taskObjective`
- `taskMetadata`

## Metadados obrigatórios
Também devem ser enviados:

- `Idempotency-Key`
- `X-Hermes-Profile`
- `X-BigHead-Organization-Id`
- `X-BigHead-Run-Id`

Se Hermes não aceitar todos esses headers, o adapter deve mapear para o formato equivalente aceito oficialmente, mas a intenção é que essa informação exista em algum lugar do contrato.

## Saída esperada
A resposta do Hermes precisa ser lida como contrato aberto, mas o BigHead vai exigir, no mínimo:

- identificador da execução
- modelo usado
- uso de tokens de entrada
- uso de tokens de saída
- conteúdo final
- sinais de erro, se houver
- qualquer metadata de tool use que Hermes exponha

## Regra de normalização
Se o Hermes não fornecer `usage`, `model` ou `providerEventId`, o run deve falhar de forma controlada.

---

# Integração com AnythingLLM

## Estratégia
O AnythingLLM será o repositório central de conhecimento do BigHead.  
Todo documento aprovado para aprendizado vai para lá.

## O que será criado

### 1. `AnythingLlmClient`
Cliente para:
- upload de documentos
- associar documento a workspace
- atualizar embeddings
- consultar workspace
- apagar conteúdo quando houver exclusão legal/operacional
- verificar existência de documento indexado

### 2. `KnowledgeIngestionService`
Serviço responsável por:
- receber documentos aprovados
- validar MIME, tamanho, checksum e tenant
- enviar para AnythingLLM
- persistir o vínculo entre artifact e documento indexado
- registrar status da indexação
- marcar falhas de ingestão com detalhe suficiente para reprocesso

### 3. `KnowledgeQuerySkill`
Skill do Hermes para consulta da base RAG.

Ela deve:
- saber quando consultar
- chamar o workspace correto
- retornar chunks relevantes
- evitar resposta direta sem contexto quando a pergunta depender de documento corporativo

---

# Fluxos Obrigatórios

## 1. Criação de agente
Quando um agente for criado no BigHead:

1. O BigHead persiste o agente.
2. O BigHead gera `agent_id` e `agent_version_id`.
3. O BigHead cria profile correspondente no Hermes.
4. O BigHead salva a versão do profile associada ao agente.
5. O BigHead registra auditoria da sincronização.
6. Se a criação do profile falhar, o agente não deve ficar ativo como “publicado”.

### Critério de aceite
- agente criado no banco
- profile criado no Hermes
- vínculo persistido
- auditoria registrada
- falha impede publicação inconsistente

---

## 2. Edição de agente
Quando um agente for editado:

1. O BigHead valida a mudança.
2. O BigHead cria nova versão do profile no Hermes.
3. O BigHead marca a versão anterior como substituída.
4. O BigHead mantém histórico completo.
5. O run novo deve usar a versão vigente.

### Critério de aceite
- nenhuma edição sobrescreve silenciosamente a versão anterior
- toda mudança gera rastreabilidade
- rollback futuro continua possível

---

## 3. Execução de run
Quando um run é disparado:

1. O BigHead cria o job.
2. O worker reclama o job.
3. O worker valida políticas e estado do agente.
4. O worker chama o Hermes via adapter.
5. Hermes executa a tarefa.
6. Se necessário, Hermes consulta AnythingLLM.
7. O worker recebe resposta.
8. O worker calcula custo.
9. O worker persiste resultado, tokens, latência e provider metadata.
10. O BigHead atualiza a UI e o estado do run.

### Critério de aceite
- execução real acontece via Hermes
- custo é registrado
- tokens são registrados
- resposta é persistida
- erros são tratados com retry ou fail conforme política

---

## 4. Ingestão de documento
Quando um documento corporativo for aprovado:

1. O BigHead salva o artifact.
2. O artifact recebe checksum e metadados.
3. O documento é enviado ao AnythingLLM.
4. O workspace correto é selecionado.
5. Embeddings são atualizados.
6. O vínculo artifact-documento é persistido.
7. O estado de ingestão fica auditável.

### Critério de aceite
- documento disponível para consulta RAG
- vínculo com tenant/workspace claro
- remoção futura possível
- falha não deixa estado ambíguo

---

# Contratos de Dados

## Profile do Hermes
Cada profile precisa conter, no mínimo:

- `name`
- `agent_id`
- `organization_id`
- `model`
- `system_prompt`
- `skills`
- `workspace`
- `version`
- `enabled`
- `risk_level`
- `created_at`
- `updated_at`

## Skill obrigatória
Deve existir uma skill padrão:
- `query_knowledge_base`

Ela deve:
- ser sempre registrada quando o recurso estiver habilitado
- ser referenciada nos profiles dos agentes que usam RAG
- ter comportamento previsível
- depender de workspace configurado por tenant

## Run metadata
Cada execução deve persistir:
- `run_id`
- `agent_id`
- `agent_version_id`
- `hermes_profile`
- `provider_event_id`
- `provider_name`
- `model`
- `input_tokens`
- `output_tokens`
- `latency_ms`
- `amount`
- `currency`
- `status`
- `error_type`
- `error_message`
- `retried`
- `used_rag`
- `used_skill_query_knowledge_base`

---

# Versionamento

## O que deve ser versionado
- profile do Hermes
- definição de skill
- schema de integração com Hermes
- schema de integração com AnythingLLM
- payload de run
- contrato de resposta
- comportamento de ingestão
- políticas de fallback
- variáveis de ambiente

## Regra
Nenhum comportamento importante pode depender de “estado atual no filesystem” sem registro em banco.

Filesystem pode ser cache operacional, mas **banco é fonte de verdade**.

---

# Medidas Obrigatórias

Cada run precisa medir e armazenar:

## 1. Latência
Separar em:
- tempo de fila
- tempo de execução Hermes
- tempo de consulta RAG
- tempo total do run

## 2. Custo por run
Registrar:
- custo total
- custo de input tokens
- custo de output tokens
- moeda
- modelo usado

## 3. Taxa de falha
Calcular:
- falha por chamada Hermes
- falha por consulta RAG
- falha por timeout
- falha por validação de schema
- falha por política/approval

## 4. Qualidade das respostas
Definir pelo menos dois modos:
- avaliação automática baseada em schema/validação
- avaliação humana em fluxos sensíveis

Se houver QA automatizado existente, ele deve ser integrado ao resultado do run.

## 5. Esforço de manutenção
Essa métrica não é técnica direta, mas deve ser acompanhada por:
- número de adapters
- número de pontos de falha
- volume de código novo
- volume de teste exigido
- incidentes por dependência externa

---

# Fallback e Falhas

## Regras de falha
Se Hermes falhar:
- o run falha de forma controlada
- o erro é classificado
- a tentativa segue política de retry
- nenhum resultado parcial é tratado como sucesso

Se AnythingLLM falhar:
- o run pode continuar sem RAG apenas se a policy do agente permitir
- se o RAG for obrigatório, o run falha
- a decisão precisa ser explícita por policy

## Importante
Não pode haver comportamento “silenciosamente degradado” sem registro.

---

# Segurança e Isolamento

## Obrigatório
- isolamento por organização
- segregação de workspace
- auditoria de acesso
- segredos server-only
- nunca expor API keys no frontend
- nunca persistir segredo em log
- nunca permitir consulta cross-tenant

## Regras de documentos
- documento só vai para workspace autorizado
- documento deve respeitar política de retenção
- exclusão lógica e física devem ser mapeáveis

---

# Variáveis de Ambiente

## Hermes
- `HERMES_API_URL`
- `HERMES_API_KEY`
- `HERMES_PROFILES_DIR`
- `HERMES_DEFAULT_MODEL`
- `HERMES_TIMEOUT_SECONDS`

## AnythingLLM
- `ANYTHING_LLM_API_URL`
- `ANYTHING_LLM_API_KEY`
- `ANYTHING_LLM_DEFAULT_WORKSPACE`
- `ANYTHING_LLM_TIMEOUT_SECONDS`

## Flags de comportamento
- `LLM_PROVIDER_DEFAULT=hermes`
- `LLM_PROVIDER_FALLBACK=<definir explicitamente>`
- `KNOWLEDGE_BACKEND=anythingllm`
- `KNOWLEDGE_BACKEND_REQUIRED=true`

---

# Testes: Especificação Exata

Vou dividir em blocos. Aqui o objetivo é evitar qualquer interpretação vaga.

---

## 1. Testes unitários

### A. `HermesProfileSync`
Deve testar:
- criação de profile com dados corretos
- atualização preservando versionamento
- remoção/desativação
- serialização YAML correta
- rejeição de dados inválidos
- normalização de path/ids

### B. `HermesRunExecutor`
Deve testar:
- monta payload correto
- envia headers corretos
- exige agente habilitado
- exige prompt publicado
- exige output schema válido
- falha se resposta não tem `providerEventId`
- falha se `usage` incompleto
- falha se tokens negativos
- calcula custo corretamente

### C. `AnythingLlmClient`
Deve testar:
- upload de documento
- atualização de embeddings
- associação ao workspace
- falha de autenticação
- falha de timeout
- falha de payload inválido
- reprocessamento idempotente

### D. `KnowledgeIngestionService`
Deve testar:
- só ingere documento aprovado
- respeita tenant/workspace
- grava vínculo no banco
- marca status correto em sucesso
- marca status correto em falha
- não perde checksum
- não reingere duplicado sem necessidade

### E. Skill de consulta
Deve testar:
- skill existe quando habilitada
- skill aponta para workspace correto
- skill usa consulta contextual
- skill retorna chunks esperados
- skill não atravessa tenant

---

## 2. Testes de integração

### A. API: criação de agente
Cenário:
- criar agente pela API
- verificar persistência no banco
- verificar sincronização Hermes
- verificar versionamento
- verificar auditoria

Critério:
- tudo persiste e sincroniza ou tudo falha junto de forma segura

### B. API: edição de agente
Cenário:
- alterar prompt/modelo/skills
- verificar nova versão de profile
- verificar histórico
- verificar consistência do agente ativo

### C. Worker: execução de run
Cenário:
- criar run válido
- worker consome job
- worker chama Hermes mockado
- Hermes devolve payload OpenAI-like
- worker registra custo/tokens/latência
- run conclui com sucesso

### D. Worker: falha Hermes
Cenário:
- Hermes retorna 500
- run entra em retry ou fail conforme policy
- erro é registrado
- não há sucesso falso

### E. Ingestão de documento
Cenário:
- subir PDF ou documento permitido
- aprovar para aprendizado
- enviar para AnythingLLM
- confirmar indexação
- persistir vínculo

### F. Falha AnythingLLM
Cenário:
- upload falha
- ingestão marca erro
- documento não fica como “indexado com sucesso”
- reprocessamento fica possível

---

## 3. Testes de contrato

### Hermes
Criar testes que validem:
- endpoint de chat
- schema mínimo de request
- schema mínimo de response
- headers obrigatórios
- comportamento de error handling

### AnythingLLM
Validar:
- endpoint de upload
- endpoint de update embeddings
- endpoint de query workspace
- campos obrigatórios da resposta
- códigos de erro mapeados

### Banco / auditoria
Validar:
- run persistido com métricas
- ingestão persistida com vínculo
- histórico de versionamento
- ausência de estado meio-salvo incoerente

---

## 4. Testes e2e / smoke

### Fluxo completo 1
- criar agente
- sincronizar Hermes
- disparar run
- obter resposta
- registrar custos
- aprovar se necessário
- verificar auditoria final

### Fluxo completo 2
- subir documento
- indexar no AnythingLLM
- perguntar ao agente algo que dependa desse documento
- verificar uso do RAG
- verificar resposta contextual
- verificar métrica de uso de conhecimento

### Fluxo completo 3
- falhar Hermes
- confirmar fallback/erro controlado
- falhar AnythingLLM
- confirmar tratamento conforme policy

---

# Critérios de Aceite Finais

A integração só é considerada concluída se:

- BigHead continua íntegro como governança
- Hermes é o executor efetivo dos runs
- AnythingLLM é a base efetiva de conhecimento
- não existe mudança visual
- agentes são versionados e sincronizados
- documentos são ingeridos e consultáveis
- métricas são capturadas por run
- erro é tratado com segurança
- testes passam
- contratos estão versionados
- não existe comportamento ambíguo ou “para depois”

---

# Decisão de Engenharia
Se a equipe vai implementar isso agora, a regra é:

**não tratar Hermes e AnythingLLM como “extras”; tratar como parte do produto.**

Isso significa:
- projeto fechado
- contrato fechado
- teste fechado
- métrica fechada
- rollback pensado
- observabilidade obrigatória

---

