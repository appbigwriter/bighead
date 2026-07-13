import { redirect } from "next/navigation";

import { createClient } from "@/lib/supabase/server";
import { signIn } from "./actions";

const messages: Record<string, string> = {
  missing_fields: "Informe e-mail e senha.",
  invalid_credentials: "E-mail ou senha invalidos.",
  signed_out: "Sessao encerrada."
};

export default async function LoginPage({
  searchParams
}: {
  searchParams: Promise<{ error?: string; status?: string }>;
}) {
  const supabase = await createClient();
  const { data } = await supabase.auth.getClaims();
  if (data?.claims) redirect("/operacao/home");

  const query = await searchParams;
  const feedback = messages[query.error ?? query.status ?? ""];

  return (
    <main className="bh-auth-page">
      <section className="bh-auth-panel" aria-labelledby="login-title">
        <span className="bh-eyebrow">BigHead</span>
        <h1 id="login-title">Entrar no workspace</h1>
        <p>Use sua conta da organizacao para acessar dados e operacoes autorizadas.</p>
        {feedback ? <p role="status" className="bh-auth-feedback">{feedback}</p> : null}
        <form action={signIn} className="bh-auth-form">
          <label htmlFor="email">E-mail</label>
          <input id="email" name="email" type="email" autoComplete="email" required />
          <label htmlFor="password">Senha</label>
          <input id="password" name="password" type="password" autoComplete="current-password" required />
          <button type="submit">Entrar</button>
        </form>
      </section>
    </main>
  );
}
