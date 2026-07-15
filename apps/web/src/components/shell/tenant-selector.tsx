"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import type { FormEvent } from "react";
import { Button } from "@bighead/ui";

import { switchTenant } from "@/app/actions/critical-mutations";
import type { WorkspaceOption } from "@/lib/mock-workspace";
import styles from "./workspace-shell.module.css";

export function TenantSelector({
  currentOrganizationId,
  organizations
}: {
  currentOrganizationId: string;
  organizations: WorkspaceOption[];
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [feedback, setFeedback] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    startTransition(async () => {
      const result = await switchTenant(data);
      setFeedback(result.message);
      if (result.ok) router.refresh();
    });
  }

  return (
    <form className={styles.tenantSelector} onSubmit={submit}>
      <label htmlFor="shell-organization">Organizacao</label>
      <div>
        <select aria-label="Organizacao" defaultValue={currentOrganizationId} disabled={pending} id="shell-organization" name="organizationId">
          {organizations.map((organization) => (
            <option key={organization.id} value={organization.id}>{organization.name}</option>
          ))}
        </select>
        <Button disabled={pending} type="submit">{pending ? "Alterando..." : "Alternar"}</Button>
      </div>
      {feedback ? <small aria-live="polite">{feedback}</small> : null}
    </form>
  );
}
