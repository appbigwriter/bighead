# Guia de Configuração de Variáveis de Ambiente — BigHead

Este guia explica como preencher, obter e ajustar as variáveis de ambiente pendentes no seu arquivo [.env.novo](file:///f:/Projetos/BigHead/.env.novo), tanto para o ambiente de desenvolvimento local quanto para o deploy em produção usando a VPS e o Easypanel.

---

## 🔑 1. Integração com Supabase (Self-Hosted)

No Supabase Self-Hosted (gerenciado pelo Easypanel no domínio `supabase.fbr.news`), as credenciais de segurança são geradas durante o deploy da infraestrutura do Supabase.

### Como obter as chaves:
1. Acesse o painel do seu **Easypanel**.
2. Vá até o projeto onde o **Supabase** está rodando.
3. Acesse as variáveis de ambiente dos serviços do Supabase (especificamente o serviço `kong` ou o contêiner de `auth`/`api`).
4. Procure pelas seguintes variáveis:
   - **`ANON_KEY`** (Corresponde à chave pública/publishable key).
   - **`SERVICE_ROLE_KEY`** (Corresponde à chave secreta do servidor/secret key).

### Ajuste no arquivo `.env.novo`:
* **`SUPABASE_PUBLISHABLE_KEY`**: Cole a **`ANON_KEY`** obtida.
* **`SUPABASE_SECRET_KEY`**: Cole a **`SERVICE_ROLE_KEY`** obtida (mantenha este segredo estritamente no backend/FastAPI).

---

## 🛢️ 2. Strings de Conexão com o Banco de Dados (`DATABASE_URL`)

O formato padrão de conexão direta com o PostgreSQL é:
`postgresql://[usuario]:[senha]@[host]:[porta]/[banco]`

### Como preencher corretamente:
* **`[usuario]`**: O padrão do Supabase é `postgres`.
* **`[senha]`**: Substitua `[YOUR-PASSWORD]` pela senha definida na instalação do Supabase (geralmente salva na variável `POSTGRES_PASSWORD` ou similar do serviço do banco de dados no Easypanel).
* **`[host]`**:
  * **Em Produção/VPS**: Se o BigHead e o Supabase estiverem rodando na mesma rede Docker do Easypanel, você pode utilizar o host interno do contêiner do banco de dados (ex: `srv-captain--supabase-db` ou o IP privado da rede Docker). Se estiver conectando externamente (não recomendado sem firewall), utilize o IP da VPS.
  * **Local (`.env.local`)**: O host padrão é `127.0.0.1:55322` (ou a porta exposta localmente).
* **`[porta]`**: O padrão interno é `5432`.
* **`[banco]`**: O banco de dados padrão do Supabase é `postgres`.

### Exemplo de edição:
```env
DATABASE_URL=postgresql://postgres:sua_senha_segura@srv-captain--supabase-db:5432/postgres
DIRECT_DATABASE_URL=postgresql://postgres:sua_senha_segura@srv-captain--supabase-db:5432/postgres
```

> [!NOTE]
> Se o seu setup Self-hosted não possui um Pooler de conexões (como o *Supavisor* ou *PgBouncer* ativo na porta `6543`), você pode utilizar a mesma string de conexão direta para **ambas** as variáveis (`DATABASE_URL` e `DIRECT_DATABASE_URL`).

---

## 🌐 3. Prefixo `NEXT_PUBLIC_` vs Sem Prefixo

O Next.js separa as variáveis por escopo de acesso por segurança:
1. **Frontend (Browser - Client Side)**: As variáveis precisam começar com `NEXT_PUBLIC_` para que o build do Next.js as exponha no navegador.
2. **Backend (FastAPI & Server Side)**: Não precisam de prefixo, permitindo o uso seguro de chaves privadas (`service_role`, credenciais de banco, etc.).

Analisando o seu arquivo [compose.production.yml](file:///f:/Projetos/BigHead/compose.production.yml), vemos que o serviço **`web`** (Next.js) e o serviço **`api`** (FastAPI) esperam variáveis específicas. 

### Ajuste no `.env.novo`:
* **Use com `NEXT_PUBLIC_`** para o Frontend:
  ```env
  NEXT_PUBLIC_SUPABASE_URL=https://supabase.fbr.news
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=eyJhbGciOiJIUz... (sua anon key)
  ```
  *(Atenção: No seu arquivo `.env.novo`, a variável estava escrita como `NEXT_SUPABASE_PUBLISHABLE_KEY`. O Next.js exige o **`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`** para ler no cliente).*
* **Use sem prefixo** para o Backend (API FastAPI e Workers):
  ```env
  SUPABASE_URL=https://supabase.fbr.news
  SUPABASE_PUBLISHABLE_KEY=eyJhbGciOiJIUz... (sua anon key)
  SUPABASE_SECRET_KEY=eyJhbGciOiJIUz... (sua service_role key)
  DATABASE_URL=postgresql://...
  ```

---

## 🧠 4. Configuração do Redis (`REDIS_URL`)

### Onde gerar? No mesmo serviço do Supabase ou do App?
O Redis deve ser configurado no **serviço do aplicativo (BigHead)**, e não do Supabase. 

Olhando o seu [compose.production.yml](file:///f:/Projetos/BigHead/compose.production.yml), **você já possui um contêiner Redis declarado no próprio projeto**. 
* Em produção (rodando via docker-compose), o compose monta a URL de conexão automaticamente utilizando o hostname do serviço:
  `REDIS_URL=redis://:[REDIS_PASSWORD]@redis:6379/0`
* Portanto, em produção, basta definir a variável **`REDIS_PASSWORD`** no painel do Easypanel (com um segredo forte à sua escolha).
* Para desenvolvimento local, você pode definir `REDIS_URL=redis://127.0.0.1:6379/0` apontando para o Redis do docker-compose local.

---

## 🛡️ 5. Malware Scanner (`MALWARE_SCANNER_URL`)

### Onde gerar?
Assim como o Redis, o scanner de malware (**ClamAV**) já está declarado como um contêiner no seu [compose.production.yml](file:///f:/Projetos/BigHead/compose.production.yml):
```yaml
clamav:
  image: clamav/clamav:1.4
  ...
```
* O próprio compose de produção injeta a URL do scanner para o worker: `clamd://clamav:3310`.
* **Ação**: Você não precisa gerar um serviço externo. Em produção, use `MALWARE_SCANNER_URL=clamd://clamav:3310`. Em desenvolvimento local, você pode deixar a variável em branco (`MALWARE_SCANNER_URL=`) caso não esteja rodando o ClamAV localmente.

---

## 🤖 6. Integração Hermes Agent (`HERMES_PROFILES_DIR`)

### Onde gerar estes parâmetros?
O `HERMES_PROFILES_DIR` define onde a API do BigHead vai salvar os perfis dos agentes em formato YAML para que o serviço Hermes possa lê-los.

* **Local (Windows)**: O caminho `f:\Projetos\BigHead\.omc\hermes\profiles` está correto.
* **Produção (VPS Linux)**: Caminhos locais do Windows não funcionam.
  1. Defina um caminho absoluto Linux válido para o contêiner, por exemplo: `/app/hermes/profiles`.
  2. No Easypanel, configure um **Volume Compartilhado (Shared Volume)** mapeado no contêiner da API e do Worker do BigHead, e monte o mesmo volume no contêiner do Hermes (ex: montando o volume `/app/hermes/profiles` em ambos). Dessa forma, quando a API do BigHead salvar um arquivo YAML, o Hermes conseguirá ler instantaneamente.

---

## 📚 7. Instalação do AnythingLLM na VPS (RAG)

Para instalar o AnythingLLM na sua VPS de maneira rápida e segura utilizando o **Easypanel**:

1. Acesse o painel do seu **Easypanel** e entre no projeto.
2. Clique em **"Add Service"** (Adicionar Serviço) ➡️ escolha **"App"** (para criar um contêiner customizado).
3. Nomeie o serviço como `anything-llm` ou `rag`.
4. Configure os seguintes campos na aba da App:
   * **Docker Image**: `mintplexlabs/anythingllm:master`
   * **Ports**: O AnythingLLM roda internamente na porta `3001`. Defina o mapeamento de portas ou aponte o domínio desejado (ex: `rag.fbr.news`) com SSL para a porta `3001` do contêiner.
   * **Volumes**: É obrigatório configurar um volume persistente para não perder seus dados/documentos. Crie um volume e mapeie:
     * *Caminho no Contêiner*: `/app/storage`
5. Clique em **Deploy**.
6. Acesse o domínio configurado (`http://rag.fbr.news`), finalize o setup inicial de administrador e navegue em **Settings > API Keys** para criar a sua chave de acesso API, que será o valor de `ANYTHING_LLM_API_KEY`.
