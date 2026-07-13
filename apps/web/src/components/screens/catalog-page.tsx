import Link from "next/link";

import { Button, Card } from "@bighead/ui";

import { areaOrder } from "@/lib/screen-catalog";
import { uiCatalog } from "@/lib/ui-catalog";
import { getServerWorkspaceData } from "@/lib/server-workspace-service";
import { getWorkspaceRequestContext } from "@/lib/workspace-request-context";
import { TransverseStateCatalog } from "./transverse-state-catalog";

export async function CatalogPage() {
  const snapshot = await getServerWorkspaceData(await getWorkspaceRequestContext());

  return (
    <section className="bh-screen">
      <Card className="bh-screen-hero-card">
        <div className="bh-screen-heading">
          <div>
            <span className="bh-eyebrow">BH-S2-01</span>
            <h2>Catalogo de componentes e estados</h2>
            <p>
              Biblioteca base da Sprint 2 para shell, estados transversais e handoff do backend.
            </p>
          </div>
          <Link className="bh-chip" href="/operacao/home">
            Voltar ao workspace
          </Link>
        </div>
      </Card>

      <div className="bh-columns">
        <Card>
          <div className="bh-card-title">
            <h3>Acoes</h3>
            <span className="bh-label">botoes, chips e states</span>
          </div>
          <div className="bh-inline">
            <Button>Primaria</Button>
            <Button tone="secondary">Secundaria</Button>
            <span className="bh-badge">Status</span>
            <span className="bh-badge bh-badge-accent">Accent</span>
            <span className="bh-badge bh-badge-risk">Risk</span>
          </div>
        </Card>

        <Card>
          <div className="bh-card-title">
            <h3>Estados</h3>
            <span className="bh-label">erro, vazio, offline, permissao</span>
          </div>
          <TransverseStateCatalog />
        </Card>
      </div>

      <Card data-testid="primitive-catalog">
        <div className="bh-card-title"><h3>Primitives universais</h3><span className="bh-label">variantes, props e acessibilidade</span></div>
        <div className="bh-catalog-grid">{uiCatalog.map((entry) => <section key={entry.name}><strong>{entry.name}</strong><p>{entry.variants.join(" · ")}</p><small>{entry.accessibility}</small></section>)}</div>
      </Card>

      <Card>
        <div className="bh-card-title">
          <h3>Cobertura da Sprint 2</h3>
          <span className="bh-label">T01-T56 agrupadas por area</span>
        </div>
        <div className="bh-catalog-grid">
          {areaOrder.map((area) => {
            const entries = snapshot.areas[area];
            return (
              <div className="bh-catalog-column" key={area}>
                <strong>{area}</strong>
                <ul className="bh-list">
                  {entries.map((entry) => (
                      <li key={entry.code}>
                        <Link href={`/${entry.slug.join("/")}`}>
                          {entry.code} - {entry.title}
                        </Link>
                      </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      </Card>
    </section>
  );
}
