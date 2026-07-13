"use client";

import { useState } from "react";
import { Button } from "@bighead/ui";

const LOG_PAGES = [["run iniciou", "step coletou contexto"], ["step chamou provider", "run finalizou"]];
const COST_PAGES = [["OpenAI · R$ 1,20"], ["Storage · R$ 0,08"]];

export function TaskOperationalPanels({ taskTitle }: { taskTitle: string }) {
  const [logPage, setLogPage] = useState(0);
  const [costPage, setCostPage] = useState(0);
  return <section aria-label="Detalhe operacional da tarefa">
    <div className="bh-state-panel" data-testid="task-detail-summary"><strong>{taskTitle}</strong><p>Resumo, SLA e estado permanecem disponiveis enquanto paineis carregam paginas.</p></div>
    <div className="bh-columns">
      <section aria-label="Logs paginados"><strong>Logs · pagina {logPage + 1}</strong><ul>{LOG_PAGES[logPage]!.map((item) => <li key={item}>{item}</li>)}</ul><Button disabled={logPage === LOG_PAGES.length - 1} onClick={() => setLogPage((page) => page + 1)} tone="secondary">Proxima pagina de logs</Button></section>
      <section aria-label="Custos paginados"><strong>Custos · pagina {costPage + 1}</strong><ul>{COST_PAGES[costPage]!.map((item) => <li key={item}>{item}</li>)}</ul><Button disabled={costPage === COST_PAGES.length - 1} onClick={() => setCostPage((page) => page + 1)} tone="secondary">Proxima pagina de custos</Button></section>
    </div>
  </section>;
}
