import Link from "next/link";

import { WorkspaceHttpError, WorkspaceMembershipError } from "@/lib/workspace-service";
import styles from "./workspace-shell.module.css";

export type WorkspaceAccessStateKind = "tenant-empty" | "permission-denied";

export function classifyWorkspaceAccessError(error: unknown): WorkspaceAccessStateKind | null {
  if (error instanceof WorkspaceMembershipError) return "tenant-empty";
  if (error instanceof WorkspaceHttpError && error.status === 403) return "permission-denied";
  return null;
}

export function WorkspaceAccessState({ kind }: { kind: WorkspaceAccessStateKind }) {
  const empty = kind === "tenant-empty";
  return (
    <div className={styles.shellState}>
      <section aria-labelledby="workspace-access-title">
        <span className="bh-eyebrow">BigHead</span>
        <h1 id="workspace-access-title">{empty ? "Configure sua organizacao" : "Acesso nao autorizado"}</h1>
        <p>{empty
          ? "Sua conta ainda nao possui uma organizacao ativa. Conclua o onboarding para entrar no workspace."
          : "Sua conta nao tem permissao para abrir este contexto. Volte ao inicio para selecionar um acesso valido."}</p>
        <Link href={empty ? "/acesso/onboarding" : "/operacao/home"} prefetch={false}>
          {empty ? "Iniciar onboarding" : "Voltar ao inicio"}
        </Link>
      </section>
    </div>
  );
}
