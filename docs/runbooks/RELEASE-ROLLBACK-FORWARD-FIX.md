# Release, rollback e forward-fix

## Princípio

Migrations são forward-only. Rollback de aplicação só é permitido quando a
versão anterior continua compatível com o schema já aplicado. Uma migration
aplicada nunca é editada; correções usam nova migration.

## Plano obrigatório da release

Registrar antes da janela:

- commit e artefatos imutáveis;
- migrations pendentes e classificação `expand`, `migrate` ou `contract`;
- ordem de banco, API, worker e web;
- duração e locks esperados;
- compatibilidade N/N-1;
- checkpoint de backup;
- smoke e métricas de sucesso;
- limiar de abortar;
- artefato anterior e forward-fix preparado para partes irreversíveis.

## Sequência recomendada

1. **Expand:** adicionar estruturas compatíveis, sem remover contrato usado.
2. Implantar API/worker capazes de ler formato antigo e novo.
3. Migrar/backfill em lote observável e retomável.
4. Trocar leitura/escrita para o formato novo.
5. Após estabilidade e confirmação de ausência de consumidores antigos,
   executar **contract** em release posterior.

## Rollback de aplicação

Usar quando não houve mudança incompatível de schema ou efeito externo:

1. Parar promoção e congelar novos deploys.
2. Registrar sintomas e horário.
3. Confirmar compatibilidade da versão anterior com o schema atual.
4. Reimplantar artefatos anteriores de API, worker e web na ordem aprovada.
5. Não reverter migration automaticamente.
6. Executar health, smoke autenticado, fila/outbox e métricas.
7. Manter incidente aberto até estabilidade e reconciliação dos efeitos.

## Forward-fix de banco

Usar quando rollback do schema é inseguro ou a migration já produziu dados:

1. Conter tráfego/escritas afetadas sem desligar auditoria.
2. Criar uma nova migration via `supabase migration new <descricao>`.
3. Reproduzir o estado em ambiente isolado e escrever teste de regressão.
4. Executar reset local, pgTAP, lint, advisors e integrações.
5. Validar em staging e revisar `db push --dry-run`.
6. Aplicar a migration corretiva sob nova aprovação.
7. Reconciliar outbox, webhooks, privacy jobs e providers por idempotency key.

## Falha durante `db push`

- Não repetir cegamente.
- Capturar a migration e erro exatos; verificar se a transação foi revertida.
- Comparar `supabase migration list` com o schema real.
- Usar `migration repair` somente se o histórico estiver comprovadamente
  incorreto; o comando não executa nem desfaz SQL.
- Se houve DDL não transacional ou efeito parcial, escrever forward-fix.

## Rollback funcional de workflow

O endpoint de rollback de workflow cria uma nova versão a partir da versão-alvo;
não altera runs históricos. Esse comportamento de domínio não substitui o
procedimento de rollback de infraestrutura ou banco.

## Encerramento

Registrar causa, impacto, dados reconciliados, migrations/artefatos finais,
tempo até recuperação, riscos residuais e ação preventiva com responsável/data.
