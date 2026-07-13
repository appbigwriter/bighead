# Backup, restore, RPO e RTO

## Objetivos

- **RPO alvo do MVP:** até 24 horas.
- **RTO alvo do MVP:** até 8 horas.

Esses alvos não estão comprovados remotamente. O teste local registrado restaurou
um snapshot lógico em 35,88 s, sem blobs de Storage e sem volume/rede de staging.

## Estratégia a aprovar por ambiente

- Confirmar plano Supabase e retenção disponível.
- Em planos pagos, verificar backup gerenciado diário; para RPO menor, avaliar e
  habilitar PITR. PITR e backup diário têm operação/retenção dependentes do plano.
- Manter export lógico off-site quando exigido por política, criptografado e com
  teste periódico.
- Inventariar buckets e objetos: dump Postgres cobre metadata de Storage, não os
  blobs.
- Registrar owner, frequência, retenção, região, criptografia e teste de restore.

## Gate local reproduzível

```powershell
pnpm db:restore-test
```

O gate restaura `auth`, `storage`, `private` e `public` em banco temporário,
compara dados e catálogo e remove resíduos. Nunca apontar o script para staging
ou produção.

## Exercício de restore em staging isolado

1. Abrir ticket de exercício; registrar backup escolhido e timestamps.
2. Confirmar que o destino é isolado e não recebe tráfego real.
3. Registrar o último evento confirmado antes do backup para medir RPO.
4. Restaurar pelo mecanismo aprovado do plano ou por dump lógico validado.
5. Aplicar somente migrations posteriores necessárias e registradas.
6. Validar:
   - Auth e memberships;
   - 54 tabelas públicas (46 de domínio e oito de integração), schemas privados,
     RLS, grants, funções e triggers;
   - contagens/hashes de amostra por tenant;
   - audit log e idempotency ledgers;
   - buckets, policies e blobs de amostra;
   - signed upload/download e quarentena;
   - Realtime, Redis reconstruído e workers;
   - health, integrações e E2E sem MSW.
7. Medir RPO e RTO reais.
8. Destruir o destino de exercício e preservar somente evidência sem secrets/PII.

## Restore durante incidente

1. Comandante declara incidente de dados e congela escritas.
2. Determinar ponto seguro anterior à corrupção; quantificar perda esperada.
3. Obter aprovações de Engenharia, Plataforma, Segurança e Produto.
4. Preferir restore em destino isolado para validação antes de corte.
5. Reconciliar efeitos externos posteriores ao ponto: pagamentos/providers,
   webhooks, outbox, publicações, privacy jobs e emails.
6. Reabrir tráfego gradualmente e monitorar integridade.

## Evidência mínima

Backup/restore point, ambiente, tamanho, início/fim, RPO/RTO medidos, hashes e
amostras, validação de blobs, divergências, aprovações e ações corretivas.

## Bloqueadores atuais de go-live

- [ ] Política/plano de backup remoto confirmado.
- [ ] PITR ou justificativa para RPO de 24 h aprovada.
- [ ] Restore de staging executado com volume representativo.
- [ ] Blobs de Storage incluídos e verificados.
- [ ] RPO e RTO remotos medidos dentro do alvo.
