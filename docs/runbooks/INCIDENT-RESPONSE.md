# Resposta a incidentes

## Severidade

| Nível | Exemplo | Acionamento inicial |
|---|---|---|
| SEV-1 | vazamento/cross-tenant, indisponibilidade ampla, perda de dados | imediato; comandante e Segurança |
| SEV-2 | função crítica degradada, filas/providers parados, erro elevado | até 15 min; Engenharia e Plataforma |
| SEV-3 | impacto limitado com workaround | horário útil; owner do domínio |
| SEV-4 | defeito sem impacto operacional imediato | backlog priorizado |

Os tempos são metas de acionamento do processo, não SLOs atualmente comprovados.

## Papéis

- **Comandante:** decide prioridade, contenção e cadência.
- **Operações:** executa ações e mantém linha do tempo.
- **Investigação:** formula/testa hipóteses sem alterar produção por tentativa.
- **Comunicação:** atualiza stakeholders com fatos confirmados.
- **Segurança/Privacidade:** obrigatório para auth, tenant, secret, portal, Storage
  ou dados pessoais.

## Primeiros 15 minutos

1. Abrir canal/ticket, declarar severidade e nomear comandante.
2. Registrar início, primeiro sintoma, ambientes e serviços afetados.
3. Preservar logs, trace IDs, audit log e IDs de eventos; não copiar payloads
   sensíveis para o canal.
4. Verificar status do Supabase e providers externos.
5. Consultar health, métricas de API/worker, conexões DB, Redis, filas, leases,
   outbox, webhook deliveries e dead-letter.
6. Conter pelo menor escopo: endpoint, tenant, provider, worker ou feature.
7. Bloquear deploys concorrentes.

## Playbooks de contenção

### Suspeita de acesso cross-tenant ou secret exposto

- Tratar como SEV-1.
- Suspender credencial/sessão afetada e rotacionar secret pelo secret manager.
- Preservar audit logs e identificar intervalo/recursos acessados.
- Não apagar evidência nem alterar RLS diretamente no remoto.
- Corrigir por migration e validar com testes adversariais antes de reabrir.

### Banco/readiness degradado

- Verificar saturação, conexões, locks, queries lentas e status da plataforma.
- Reduzir carga/consumidores antes de escalar compute.
- Não executar reset ou restore sem declaração de incidente de dados e aprovação.

### Redis, worker ou fila

- Verificar heartbeat, idade do item mais antigo, retries e leases expirados.
- Reiniciar consumidor somente após confirmar recuperação idempotente.
- Não ACK manualmente trabalho cujo efeito externo não foi reconciliado.

### Webhook/provider externo

- Confirmar status do provider e bloquear somente o adapter afetado.
- Preservar delivery/event ID; o consumidor é at-least-once.
- Reprocessar dead-letter apenas após corrigir causa e confirmar idempotência.

### Auth/SMTP/OAuth

- Verificar status Supabase Auth, callback, SMTP e rate limits.
- Evitar mensagens que enumerem usuários.
- Após revogação crítica, considerar que JWT já emitido pode permanecer válido
  até expirar; aplicar a contenção prevista para sessões.

## Comunicação

Cada atualização deve conter: horário, impacto conhecido, hipótese/causa
confirmada, contenção em curso, risco de dados, próximo checkpoint e responsável.
Não informar ETA sem evidência.

## Recuperação e encerramento

- Health e smoke críticos estáveis pelo período definido pelo comandante.
- Backlog/fila reconciliado sem duplicação.
- Integridade e isolamento de tenant verificados.
- Dados perdidos/restaurados quantificados contra RPO.
- Comunicação final enviada.
- Postmortem sem culpa em até cinco dias úteis para SEV-1/SEV-2, com ações,
  responsáveis e datas.
