# Reindex de embeddings e recuperacao CRM

## Troca controlada de embedding

A dimensao operacional e obtida por `public.active_embedding_dimensions()`. O banco aceita
vetores de 1 a 2000 dimensoes, mas nunca troca o perfil ativo no inicio do reprocessamento.
Somente a API/worker com conexao `service_role` pode operar as funcoes em `private`.

1. Criar o run com
   `private.start_embedding_reindex(provider, model_name, dimensions, actor_user_id)`.
2. Gerar cada novo vetor e gravar no staging com
   `private.complete_embedding_reindex_item(run_id, entity_type, entity_id, embedding)`.
3. Conferir que o run chegou a `ready`. Enquanto houver linha pendente ou com dimensao
   incorreta, a ativacao e rejeitada e o perfil anterior continua atendendo buscas.
4. Obter os comandos com `private.embedding_reindex_index_commands(run_id)` e executar cada
   `CREATE INDEX CONCURRENTLY` retornado em autocommit, fora de qualquer bloco transacional.
   Confirmar que todos os comandos terminaram antes de continuar.
5. Executar `private.activate_embedding_reindex(run_id)` em janela controlada. A funcao valida
   que os indices HNSW esperados existem e estao prontos, troca os vetores em uma transacao e
   ativa o novo perfil. Se algum indice nao estiver pronto, a ativacao falha com
   `embedding_reindex_indexes_not_ready` e preserva o perfil anterior.
6. Rodar `pnpm db:performance-test` e comparar p95/plan antes de liberar trafego.

Somente um run pode ficar `running|ready`. Um lock transacional serializa start, enqueue e
ativacao. Inserts e alteracoes de conteudo durante o run criam item pendente e devolvem o run a
`running`; portanto a ativacao nao ignora uma linha confirmada antes dela. Solicitar reindex do
perfil ja ativo e rejeitado sem alterar o perfil operacional.

Nao remova o perfil/indice anterior antes da validacao e do backup. O provider de embeddings
real, custo, rate limit e qualidade semantica precisam ser homologados no ambiente de staging;
os testes locais comprovam migracao, dimensao, rollback transacional implicito e plano, nao a
qualidade do modelo externo.

## Importacao CRM parcial

`POST /v1/crm/imports` persiste o agregado em `crm_imports` e uma linha em `crm_import_rows`
para cada entrada. Linhas invalidas ficam `failed` sem apagar as aceitas. Para corrigir apenas
essas linhas, envie seus numeros e payloads corrigidos a
`POST /v1/crm/imports/{importId}/resume`. A API rejeita linhas ja aceitas por outro payload e
recalcula `partial|completed` na mesma transacao que cria/atualiza as entidades CRM. Um lock por
import serializa concorrentes. Replay com o mesmo fingerprint nao incrementa `attempts`; payload
divergente depois da primeira conclusao recebe `409`.

Antes de repetir uma retomada apos timeout, consulte o import original: a chave derivada do
payload torna o comando idempotente. Registros de relatorio restringem exclusao das entidades
referenciadas; a politica de retencao deve expirar primeiro o relatorio, com auditoria.

## Merge de conta duplicada

`POST /v1/crm/accounts/{sourceId}/merge` exige `targetAccountId` e motivo. Sob lock transacional,
o banco move contatos, leads e oportunidades, grava `merged_into_id/merged_at` na origem e anexa
`crm.account.merged` ao log imutavel. A conta fonte nao e apagada. Nao execute merges cruzando
tenants nem tente mesclar uma origem/destino ja tombstonado.
