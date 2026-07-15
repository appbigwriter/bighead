import { redirect } from "next/navigation";
import { Button } from "@bighead/ui";

import { createClient } from "@/lib/supabase/server";
import { submitOnboarding } from "./actions";

const messages: Record<string, string> = {
  missing_fields: "Preencha nome, organizacao e slug.",
  submit_failed: "Nao foi possivel concluir o onboarding agora.",
  invalid_session: "Sua sessao expirou. Entre novamente."
};

export default async function OnboardingPage({
  searchParams
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const supabase = await createClient();
  const { data } = await supabase.auth.getClaims();
  if (!data?.claims) redirect("/login");

  const query = await searchParams;
  const feedback = messages[query.error ?? ""] ?? null;

  return (
    <main className="bh-auth-page">
      <section className="bh-auth-panel" aria-labelledby="onboarding-title">
        <header className="bh-auth-heading">
          <span className="bh-eyebrow">Acesso inicial</span>
          <h1 id="onboarding-title">Configure sua organizacao</h1>
          <p>Crie a primeira organizacao e conclua a entrada no workspace.</p>
        </header>
        {feedback ? <p role="status" className="bh-auth-feedback">{feedback}</p> : null}
        <form action={submitOnboarding} className="bh-auth-form">
          <label htmlFor="displayName">Seu nome</label>
          <input id="displayName" name="displayName" autoComplete="name" defaultValue="Owner" required />
          <label htmlFor="organizationName">Organizacao</label>
          <input id="organizationName" name="organizationName" defaultValue="BigHead" required />
          <label htmlFor="organizationSlug">Slug da organizacao</label>
          <input id="organizationSlug" name="organizationSlug" defaultValue="bighead" pattern="^[a-z0-9][a-z0-9-]{1,62}$" required />
          <label htmlFor="timezone">Fuso horario</label>
          <input id="timezone" name="timezone" defaultValue="America/Sao_Paulo" required />
          <label htmlFor="locale">Idioma</label>
          <input id="locale" name="locale" defaultValue="pt-BR" required />
          <label htmlFor="goals">Metas</label>
          <input id="goals" name="goals" placeholder="qualidade, velocidade" />
          <label htmlFor="approvalPolicy">Politica inicial</label>
          <input id="approvalPolicy" name="approvalPolicy" defaultValue='{"highRisk":"manual"}' />
          <Button type="submit">Criar organizacao e entrar</Button>
        </form>
      </section>
    </main>
  );
}
