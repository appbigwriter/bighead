"use client";

import { useState } from "react";

import { Button, Card } from "@bighead/ui";

import type { PortalPreview } from "@/lib/workspace-service";
import { decidePortal, type MutationResult } from "@/app/actions/critical-mutations";

export function PortalExperience({ preview }: { preview: PortalPreview }) {
  const [decision, setDecision] = useState("pending");
  const [comment, setComment] = useState("");
  const [result, setResult] = useState("Nenhuma resposta enviada.");
  const [mutation, setMutation] = useState<MutationResult | null>(null);
  const [pending, setPending] = useState(false);
  const [idempotencyKey] = useState(() => crypto.randomUUID());
  const blocked = preview.state !== "valid";

  return (
    <main className="bh-portal">
      <Card className="bh-screen-hero-card">
        <div className="bh-screen-heading">
          <div>
            <span className="bh-eyebrow">T24 • Portal externo</span>
            <h2>{preview.title}</h2>
            <p>{preview.summary}</p>
          </div>
          <span className={`bh-badge ${blocked ? "bh-badge-risk" : "bh-badge-accent"}`}>
            Token {preview.state}
          </span>
        </div>
      </Card>

      <div className="bh-columns">
        <Card>
          <div className="bh-card-title">
            <h3>Escopo do link</h3>
            <span className="bh-label">{preview.dueLabel}</span>
          </div>
          <ul className="bh-list">
            {preview.allowedActions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Card>

        <Card>
          <div className="bh-card-title">
            <h3>Guard rails</h3>
            <span className="bh-label">Requested by {preview.requestedBy}</span>
          </div>
          <ul className="bh-list">
            {preview.guardRails.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Card>
      </div>

      <div className="bh-columns">
        <Card>
          <div className="bh-card-title">
            <h3>Decisao externa</h3>
            <span className="bh-label">aprovacao, rejeicao ou pedido de alteracao</span>
          </div>
          <div className="bh-inline">
            {["approved", "changes_requested", "rejected"].map((value) => (
              <Button
                disabled={blocked}
                key={value}
                onClick={() => setDecision(value)}
                tone={decision === value ? "primary" : "secondary"}
              >
                {value}
              </Button>
            ))}
          </div>
          <label className="bh-field">
            <span>Comentario</span>
            <textarea
              aria-label="Comentario externo"
              disabled={blocked}
              onChange={(event) => setComment(event.target.value)}
              placeholder="Explique sua revisao"
              value={comment}
            />
          </label>
          <Button disabled={blocked || pending || decision === "pending"} onClick={() => {
            const form = new FormData();
            form.set("token", preview.token); form.set("decision", decision); form.set("comment", comment);
            form.set("expectedRound", String(preview.expectedRound)); form.set("idempotencyKey", idempotencyKey);
            setPending(true);
            void (async () => {
              const response = await decidePortal(form);
              setMutation(response);
              setResult(response.message);
              setPending(false);
            })();
          }}>{pending ? "Enviando..." : "Enviar resposta"}</Button>
        </Card>

        <Card>
          <div className="bh-card-title">
            <h3>Status do portal</h3>
            <span className="bh-label">link isolado do shell interno</span>
          </div>
          <div className={`bh-state-panel ${blocked ? "bh-state-panel-risk" : ""}`} role="status">
            <strong>{blocked ? "Link bloqueado" : mutation && !mutation.ok ? `Falha HTTP ${mutation.status}` : "Link pronto para decisao"}</strong>
            <p>{blocked ? "O token nao aceita mais resposta e mostra apenas o escopo permitido." : result}</p>
          </div>
        </Card>
      </div>
    </main>
  );
}
