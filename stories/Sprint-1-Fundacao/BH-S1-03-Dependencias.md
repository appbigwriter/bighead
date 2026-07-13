# BH-S1-03 - Instalacao e fixacao de dependencias

**Dominio:** Infra  
**Depende de:** BH-S1-01, BH-S1-02  
**Estimativa:** 5 pontos

## Historia

Como desenvolvedor, quero dependencias instaladas e fixadas para reproduzir builds e reduzir risco de supply chain.

## Escopo

- Instalar as dependencias aprovadas em `prd/04-Dependencias.md`, resolvendo as decisoes antes marcadas como alternativas.
- Decisoes default para revisao: Tailwind CSS; Radix/shadcn; TanStack Query/Table; TipTap; React Flow; Recharts; FastAPI; SQLAlchemy async; asyncpg; Alembic; Redis + ARQ; HTTPX; Tenacity; pgvector; OpenTelemetry.
- Fixar Node, pnpm e Python; gerar lockfiles; configurar Renovate/Dependabot.
- Configurar auditoria (`pnpm audit`, `pip-audit`), licencas e SBOM.

## Criterios de aceite

- [ ] Lockfiles sao versionados e builds nao usam `latest`.
- [ ] Pacotes duplicados ou de funcao equivalente possuem justificativa.
- [ ] Dependencias de producao e desenvolvimento estao separadas.
- [ ] Auditorias nao possuem vulnerabilidade critical/high sem waiver documentado.
- [ ] Bundle inicial e imagem backend possuem baseline de tamanho registrada.
- [ ] ADR registra escolhas ARQ, Recharts e React Flow.

## Casos de borda

- [ ] Dependencia abandonada bloqueia aceite ate substituicao ou waiver.
- [ ] Pacote com licenca incompatível nao entra no lockfile final.

## Fora de escopo

- Implementar os recursos fornecidos pelas bibliotecas.
