import { redirect } from "next/navigation";
import { Button } from "@bighead/ui";

import { createClient } from "@/lib/supabase/server";
import { updatePassword } from "./actions";

export default async function UpdatePasswordPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const supabase = await createClient();
  const { data } = await supabase.auth.getClaims();
  if (!data?.claims) redirect("/login?error=invalid_callback");
  const query = await searchParams;

  return (
    <main className="bh-auth-page">
      <section className="bh-auth-panel" aria-labelledby="password-title">
        <span className="bh-eyebrow">BigHead</span>
        <h1 id="password-title">Definir nova senha</h1>
        <p>Use pelo menos 12 caracteres.</p>
        {query.error ? <p role="alert" className="bh-auth-feedback">Nao foi possivel atualizar a senha.</p> : null}
        <form action={updatePassword} className="bh-auth-form">
          <label htmlFor="password">Nova senha</label>
          <input id="password" name="password" type="password" minLength={12} autoComplete="new-password" required />
          <Button type="submit">Atualizar senha</Button>
        </form>
      </section>
    </main>
  );
}
