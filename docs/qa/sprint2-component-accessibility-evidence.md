# Sprint 2 - catalogo, responsividade e acessibilidade

## Matriz comprovada

| Superficie | Desktop | Mobile | Evidencia |
|---|---:|---:|---|
| Loading | PASS | PASS | `StatePanel(kind="loading")`, `aria-busy` e skeleton |
| Vazio | PASS | PASS | CTA nomeada e focavel |
| Erro | PASS | PASS | `role="alert"` e retry |
| Offline | PASS | PASS | `role="status"` e reconexao |
| Sem permissao | PASS | PASS | nenhum dado, contador ou acao protegida |
| Sucesso | PASS | PASS | proxima acao nomeada |

O mesmo componente responsivo renderiza as duas larguras. A suite Playwright registrada na
Sprint executa o catalogo nos projetos desktop e mobile e valida Axe sem violacoes critical ou
serious nas jornadas criticas. A suite semantica `transverse-states.test.tsx` percorre todos os
controles por foco de teclado; `journeys.spec.ts` valida foco visivel com Tab, reduced motion,
zoom 200% e ausencia de overflow em 360, 768, 1280 e 1920 px.

Em 2026-07-13, o caso focado foi reexecutado contra o dev server existente, sem build ou novo
webServer: `playwright test --config playwright.reuse.config.ts --grep "shell inicial"`.
Resultado: desktop Chromium `PASS`, mobile Pixel 5 `PASS` (2/2). Em cada viewport, teclado real
percorreu ate 40 controles com foco visivel; na command palette, `ArrowDown` moveu foco ao
primeiro atalho e `Alt+1` o executou. Axe passou nas duas rotas sem violacao critical/serious.

A suite oficial completa foi reexecutada novamente em 2026-07-14 depois das correcoes do
fallback `ScreenExperience` T01-T56, dos primitives compartilhados, do contraste WCAG e do
seletor E2E. Resultado: 34/34 execucoes aprovadas em desktop/mobile, incluindo as varreduras
Axe das jornadas. O E2E real, sem MSW, passou 20/20 nos mesmos projetos desktop/mobile e
tambem executou Axe.

Revisao independente final: `PASS` para a evidencia automatizada de Axe e teclado. O revisor
nao autorizou tratar a automacao como execucao manual; o checkbox literal de navegacao manual
em BH-S2-01 permanece aberto ate uma sessao humana ou interativa documentada.

## Catalogo interno

`/catalogo` e o catalogo oficial do projeto, sem dependencia Storybook. Ele documenta variantes
e requisitos de acessibilidade de `Button`, `Dialog` e `StatePanel`, alem dos seis estados
transversais. Novas telas devem importar esses primitives de `@bighead/ui`; botao, dialogo e
erro local ad hoc nao fazem parte da fronteira suportada.

## Preferencias sem flash

O script inline de `app/layout.tsx` aplica tema, densidade e movimento no elemento `html` antes
do `body`. Alteracoes atualizam DOM e `localStorage` sincronicamente e depois sincronizam o
mesmo payload por `PATCH /v1/preferences`. O teste de bootstrap inspeciona as tres propriedades;
os testes do controle e da server action comprovam persistencia local e contrato HTTP.
