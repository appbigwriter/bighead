import { redirect } from "next/navigation";
import { Button } from "@bighead/ui";

import { createClient } from "@/lib/supabase/server";
import { readSupabaseAuthRuntimeConfig } from "@/lib/supabase/auth-config";
import { requestMagicLink, requestPasswordReset, signIn, signUp } from "./actions";

const messages: Record<string, string> = {
  missing_fields: "Informe e-mail e senha.",
  invalid_credentials: "E-mail ou senha inválidos.",
  signed_out: "Sessão encerrada.",
  invalid_callback: "Link inválido ou expirado. Solicite um novo e-mail.",
  missing_email: "Informe seu e-mail.",
  email_sent: "Se a conta existir, enviaremos as instruções por e-mail.",
  password_updated: "Senha atualizada. Entre novamente.",
  signup_sent: "Conta criada. Se houver confirmação de e-mail, verifique sua caixa de entrada."
};

export default async function LoginPage({
  searchParams
}: {
  searchParams: Promise<{ error?: string; status?: string }>;
}) {
  const supabase = await createClient();
  const { data } = await supabase.auth.getClaims();
  if (data?.claims) redirect("/operacao/home");

  const { smtpConfigured } = readSupabaseAuthRuntimeConfig();
  const query = await searchParams;
  const feedback = messages[query.error ?? query.status ?? ""];

  return (
    <main className="bh-auth-page">
      <section className="bh-auth-intro" aria-label="BigHead">
        <span className="bh-auth-mark" aria-hidden="true">BH</span>
        <div>
          <p className="bh-auth-brand">BigHead</p>
          <h2>Decisões claras.<br />Operação conectada.</h2>
          <p>Um workspace seguro para transformar sinais em trabalho coordenado.</p>
        </div>
        <p className="bh-auth-trust">Acesso protegido por organização</p>
      </section>

      <section className="bh-auth-panel" aria-labelledby="login-title">
        <header className="bh-auth-heading">
          <span className="bh-eyebrow">Acesso ao workspace</span>
          <h1 id="login-title">Boas-vindas</h1>
          <p>Entre com sua conta da organização.</p>
        </header>
        {feedback ? <p role="status" className="bh-auth-feedback">{feedback}</p> : null}
        <form action={signIn} className="bh-auth-form">
          <label htmlFor="email">E-mail</label>
          <input id="email" name="email" type="email" autoComplete="email" required />
          <label htmlFor="password">Senha</label>
          <input id="password" name="password" type="password" autoComplete="current-password" required />
          <div className="bh-auth-actions">
            <Button type="submit">Entrar</Button>
            <Button formAction={signUp} tone="secondary" type="submit">Criar conta</Button>
          </div>
        </form>

        <details className="bh-auth-alternatives">
          <summary>Outras formas de acesso</summary>
          <form action={requestMagicLink} className="bh-auth-form">
            <label htmlFor="magic-email">Entrar sem senha</label>
            <input id="magic-email" name="email" type="email" autoComplete="email" required />
            <Button type="submit" tone="secondary">Enviar link de acesso</Button>
          </form>
          <form action={requestPasswordReset} className="bh-auth-form">
            <label htmlFor="recovery-email">Esqueci minha senha</label>
            <input id="recovery-email" name="email" type="email" autoComplete="email" required />
            <Button type="submit" tone="secondary">Enviar recuperação</Button>
          </form>
        </details>

        {!smtpConfigured ? (
          <section className="bh-auth-local-access" aria-labelledby="local-access-title">
            <header className="bh-auth-heading">
              <span className="bh-eyebrow">Supabase local</span>
              <h2 id="local-access-title">Acesso de emergência</h2>
              <p>Sem SMTP local, os e-mails não saem. Use a conta seedada para destravar o projeto.</p>
            </header>
            <form action={signIn} className="bh-auth-form">
              <label htmlFor="local-email">E-mail local</label>
              <input id="local-email" name="email" type="email" autoComplete="email" defaultValue="owner@atlas.bighead.dev" required />
              <label htmlFor="local-password">Senha local</label>
              <input id="local-password" name="password" type="password" autoComplete="current-password" defaultValue="BigHeadLocalOnly!2026" required />
              <Button type="submit">Entrar com conta local</Button>
            </form>
          </section>
        ) : null}
      </section>
    </main>
  );
}
