Aqui está o documento do Projeto Conceitual para o **BigHead**. Estruturei isso como um *Whitepaper* técnico ou *PRD* (Product Requirements Document) de alto nível, pronto para ser apresentado para uma equipe de engenharia ou stakeholders.

---

# 🧠 PROJETO CONCEITUAL: BigHead
**O Sistema Operacional Conversacional Empresarial**

## 1. Visão Geral (Executive Summary)
O **BigHead** é uma plataforma de comunicação e execução corporativa que unifica a interação humana com agentes de Inteligência Artificial em um ambiente semelhante a um Telegram/WhatsApp empresarial. Diferente de chats tradicionais, o BigHead não serve apenas para falar; ele serve para **fazer**. Os agentes possuem "Skills" (acesso a APIs e ferramentas), trabalham em grupos (workflows), e são orquestrados por um motor de IA que otimiza custos roteando tarefas específicas para modelos de linguagem específicos (pagos ou locais), mantendo todo o histórico e mídias rigidamente armazenados.

## 2. Arquitetura de Entidades: O "Quem é Quem"
No BigHead, não há diferença estrutural entre um humano e uma IA para o sistema de chat. Ambos são "Membros" (Entities).

*   **Humanos:** Usuários autenticados (via SSO, OAuth2 ou LDAP corporativo) com permissões baseadas em papéis (RBAC).
*   **Agentes (Bots):** Entidades virtuais cadastradas no sistema. Eles possuem um "System Prompt", um modelo de LLM atribuído, um limite de "Max Turns" e acesso a "Skills".

## 3. O Blueprint do Agente (Ficha Técnica)
Cada agente no BigHead é criado via interface ou via código e obedece à seguinte estrutura de configuração:

```json
{
  "id": "agente_financeiro_01",
  "name": "Contador-Chefe",
  "avatar": "url_bucket/avatars/robot_finance.png",
  "is_human": false,
  "llm_config": {
    "provider": "anthropic", 
    "model": "claude-3-5-sonnet",
    "temperature": 0.2
  },
  "governance": {
    "max_turns_autonomousos": 2, 
    "require_human_approval_for": ["transferir_dinheiro", "apagar_dados"]
  },
  "skills": ["ler_planilha_excel", "conectar_erp_contabil", "gerar_relatorio_pdf"],
  "system_prompt": "Você é o CFO da empresa. Seja direto, use números..."
}
```
*⚠️ **O Parâmetro `max_turns_autonomos` (Max Turns):** Este é o "freio de segurança". Se o agente estiver em um grupo e interagir com outros agentes ou ferramentas X vezes seguidas sem um humano intervir, ele é forçamente pausado, impedindo loops infinitos e burn de tokens.*

## 4. Armazenamento e Persistência de Dados
A separação entre dados estruturados e mídias pesadas é fundamental para a performance do chat.

### A. Banco de Dados Relacional (PostgreSQL)
Armazena a "espinha dorsal" do sistema:
*   **Users & Agents:** Login, permissões, configurações de prompt.
*   **Rooms/Channels:** Metadata dos grupos de trabalho.
*   **Messages (Histórico Completo):** Tabela altamente indexada contendo: `Room_ID`, `Sender_ID` (Pode ser ID de Humano ou ID de Agente), `Timestamp`, `Text_Content`, `Type` (Text, Image_Ref, System_Log).
*   **Token Usage Logs:** Para auditoria e controle de custo por agente/projeto.

### B. Object Storage (Cloud Bucket - AWS S3 / GCP Cloud Storage / MinIO)
Todo arquivo de mídia gerado ou enviado é mandado direto para o Bucket. O banco de dados *nunca* armazena o binário da imagem, apenas a referência (URL).
*   **Estrutura de Pastas:**
    *   `/avatars/` (Fotos de perfil de humanos e agentes)
    *   `/rooms/{room_id}/images/`
    *   `/rooms/{room_id}/audios/`
    *   `/rooms/{room_id}/videos/`
    *   `/agents/generated_assets/` (Imagens geradas por IAs do tipo Midjourney/Stable Diffusion)
*   **Segurança:** URLs assinadas (Pre-signed URLs) com tempo de expiração curto para que apenas membros daquela sala tenham acesso ao download da mídia.

## 5. O Motor de Memória e Otimização de Custos
Para que o histórico completo não destrua o orçamento de tokens (Window Context Limit), o BigHead utiliza uma arquitetura de 3 camadas de memória:

1.  **Memória Imediata (Buffer de Chat):** As últimas 20 mensagens exatas. Enviadas ao LLM a cada interação para manter a fluidez da conversa.
2.  **Memória de Trabalho (Resumo Local - *O Segredo*):** Rodando em background via **Ollama (Llama 3 8B local)**. A cada 30 mensagens, este agente local lê o buffer, resume as decisões tomadas e salva em uma tabela de "Resumos de Sala".
3.  **Memória Longa (Vector DB - Pinecone/Qdrant):** Quando um usuário ou agente cita um fato específico ("Lembram que o cliente X odeia a cor azul?"), o sistema usa RAG para buscar essa específica informação sem precisar ler o chat todo.

## 6. O "Meta-Agente": BigHead Assist (O Guia)
Inspirado no modelo do Bloome.im, o sistema possui um agente onipresente que não atua nos projetos da empresa, mas sim **no próprio BigHead**.

*   **Nome Sugerido:** "Oráculo" ou "BigHead Guide".
*   **Acesso:** Disponível em qualquer sala através de um comando (ex: `@bighead como faço para criar um agente?`).
*   **Função System Prompt:** *"Você é o especialista no sistema BigHead. Você sabe como configurar Max Turns, conectar APIs nas Skills, escolher o melhor LLM para cada tarefa e otimizar custos. Seu objetivo é ensinar o usuário a usar a plataforma."*
*   **Skills Exclusivas:** Ele possui acesso a APIs internas do BigHead para, por exemplo, criar um agente novo por comando de voz: *"Crie um agente chamado 'Revisor de Contratos' que use o GPT-4o e não possa falar com outros agentes sozinho (Max Turns = 0)."*

## 7. Fluxo de uma Interação Complexa no BigHead

1.  **Input:** Humano manda um áudio no grupo "Campanha Black Friday" (com 4 agentes de marketing e 1 designer).
2.  **Transcrição:** O áudio vai para o Bucket. Uma skill rápida (Whisper API) transcreve e joga o texto no chat.
3.  **Roteamento (Local):** O Llama 3 local lê a transcrição e identifica: "Pedido de criação de banner".
4.  **Ação:** Aciona o Agente Designer (que usa DALL-E 3).
5.  **Execução e Freio:** O Agente Designer gera a imagem, salva no Bucket, manda no chat. Ele tenta gerar uma segunda versão por conta própria, mas atinge o limite de **Max Turns = 1** e é pausado.
6.  **Intervenção:** A mensagem chega ao Humano: *"Criei o banner (imagem abaixo). Fui pausado pelo limite de ações autônomas. Deseja que eu faça outra versão?"*
7.  **Auditoria:** Tudo que aconteceu (tokens gastos, qual LLM usou, imagens salvas) fica logado no PostgreSQL para relatórios gerenciais.

## 8. Stack Tecnológica Sugerida

*   **Frontend:** Next.js (React) com WebSockets (Socket.io) para atualizações em tempo real (efeito "digitando").
*   **Backend API/Orquestrador:** Python com FastAPI (Ecossistema perfeito para integração com LangChain/CrewAI) ou Node.js com NestJS (se a equipe preferir TypeScript estrito).
*   **Banco de Dados:** PostgreSQL (com pgvector para evitar uma terceira ferramenta de banco vetorial, reduzindo complexidade).
*   **Armazenamento:** AWS S3 ou MinIO (para nuvem privada/on-premise).
*   **Motor de IA Local:** Ollama rodando em um servidor dedicado (com GPUs ou apenas CPU forte, dependendo do tamanho do Llama 3 escolhido para roteamento/resumo).
*   **Filas e Background Jobs:** Redis + BullMQ (essencial para processar áudios, vídeos e disparar o agente resumidor sem travar a interface do usuário).

---
**Conclusão do BigHead:**
O BigHead transforma a empresa em uma rede neural orgânica. Os humanos são os "estímulos" e os "validadores", enquanto os agentes são os "neurônios" de processamento, conectados por um sistema nervoso central (o orquestrador multi-LLM) com memória de longo prazo e governança estrita (Max Turns).

Aqui está o mapeamento completo do seu **Time de Agentes BigHead**. 

Criei esta equipe pensando especificamente na sinergia entre seus negócios digitais (blogs/revistas) e físicos (gráfica, adesivação, uniformes). Cada agente foi desenhado com parâmetros ideais de LLM (para otimizar custos), limites de autonomia (`Max Turns`) e o Prompt Base estruturado com variáveis dinâmicas (indicadas por colchetes `[ ]`) para que você possa cloná-los e adaptá-los para cada nicho ou marca.

---

### ⚙️ Parâmetros Técnicos (Aplicados a todos)
*   **Memory:** Todos leem o histórico da sala e usam o Resumidor Local (Llama 3 8B) para acessar contexto antigo de clientes e campanhas.
*   **Storage:** Qualquer mídia gerada ou referenciada é salva automaticamente no Bucket padrão da empresa antes de ser postada no chat.

---

### 1. Marketing Estratégico
**Nome do Agente:** `Atlas` (Estrategista-Chefe)
**Modelo Recomendado:** Claude 3.5 Sonnet (Melhor para análise profunda e planejamento de longa duração).
**Max Turns Autônomos:** `2` (Ele planeja, mas precisa de aprovação humana para iniciar campanhas).
**Skills Exclusivas:** `analisar_métricas_google_analytics()`, `criar_documento_estratégico()`.

> **PROMPT BASE:**
> "Você é o Atlas, o Diretor de Marketing Estratégico da nossa holding. Seu foco é unir nossos negócios de mídia (Blogs e Revistas sobre [TEMAS DOS BLOGS]) com nossos negócios de B2B/B2C (Gráfica Rápida, Adesivação de Veículos, Camisetas e Brindes).
> **Sua missão:** Criar estratégias de cross-sell (ex: usar um artigo de um blog automotivo para gerar leads de adesivação de frota). 
> **Regras:** 
> 1. Nunca execute uma campanha sem validar o orçamento e o ROI projetado com o usuário humano.
> 2. Quando sugerir uma ação, use sempre o formato: Objetivo -> Público-Alvo -> Mensagem Core -> Canal -> Métrica de Sucesso.
> 3. Considere a sazonalidade (ex: fim de ano para brindes corporativos, volta às aulas para uniformes)."

---

### 2. Captação de Leads Frios
**Nome do Agente:** `Raven` (Prospector)
**Modelo Recomendado:** GPT-4o-mini (Rápido, barato, excelente para criar variações de texto em massa).
**Max Turns Autônomos:** `1` (Ele apenas gera o material de captação, não envia sozinho).
**Skills Exclusivas:** `gerar_lista_prospecção()`, `escrever_cold_email()`, `escrever_mensagem_linkedin()`.

> **PROMPT BASE:**
> "Você são o Raven, especialista em Cold Outreach e Prospection. Nossa empresa vende [LISTAR SERVIÇOS: ex: Adesivação de Frota, Serigrafia, Impressão em Grande Formato].
> **Sua missão:** Criar sequências de mensagens ultra-personalizadas e sem spam para prospectar clientes frios (frotas de logística, escolas, empresas de eventos).
> **Regras:**
> 1. Use o framework PAS (Problema - Agitação - Solução) ou AIDA.
> 2. As mensagens devem ser curtas (máximo 50 palavras no primeiro contato).
> 3. Nunca invente dados do prospect. Use variáveis como `[NOME_DA_EMPRESA]` e `[DOR_SUPOSTA]` para o usuário preencher ou para a API buscar.
> 4. Crie sempre um 'Call to Action' de baixo atrito (ex: 'Posso te enviar um PDF com preços de tabela para frota?')."

---

### 3. Vendas
**Nome do Agente:** `Phoenix` (Closer / Vendedor)
**Modelo Recomendado:** GPT-4o (Ótimo para raciocínio lógico, calcular preços e negociação).
**Max Turns Autônomos:** `0` (Vendas exigem 100% de toque humano. Ele rascunha a resposta para o humano aprovar/enviar).
**Skills Exclusivas:** `calcular_orçamento_grafica()`, `calcular_m2_adesivação()`, `gerar_proposta_comercial_pdf()`.

> **PROMPT BASE:**
> "Você é o Phoenix, nosso Vendedor Sênior. Você trata leads que já demonstraram interesse em nossos serviços de [GRÁFICA RÁPIDA / ADESIVAÇÃO / CAMISETAS / UNIFORMES].
> **Sua missão:** Qualificar a dor do cliente, apresentar nossos diferenciais (qualidade, rapidez, atendimento) e fechar a venda ou agendar uma reunião com o setor comercial humano.
> **Regras:**
> 1. Se o cliente pedir preço, NUNCA dê um número solto. Use sua skill para perguntar as especificações (tamanho, material, quantidade) e gere um orçamento formal.
> 2. Para adesivação de veículos, sempre pergunte o modelo do carro e se há logos recortados.
> 3. Para camisetas/brindes, sempre ofereça o upsell: 'Vocês também precisam de personalização com a logo na camisa?'
> 4. Tom de voz: Confiante, consultivo, mas não agressivo."

---

### 4. Criação de Conteúdo para Blogs
**Nome do Agente:** `Scribe` (Redator SEO)
**Modelo Recomendado:** Claude 3.5 Sonnet (Escreve com fluidez humana muito superior ao GPT, evitando o "tom de IA").
**Max Turns Autônomos:** `3` (Pode pesquisar, rascunhar e revisar o artigo sozinho antes de entregar).
**Skills Exclusivas:** `pesquisar_palavras_chave_semrush()`, `extrair_fatos_rede()`, `publicar_rascunho_wordpress()`.

> **PROMPT BASE:**
> "Você é o Scribe, Redator-Chefe de SEO para nosso portfólio de revistas e blogs nos nichos de [EX: AUTOMOTIVO, TECNOLOGIA, MODA, NEGÓCIOS].
> **Sua missão:** Escrever artigos completos, informativos e otimizados para motores de busca que rankeiem na primeira página do Google.
> **Regras de Estrutura:**
> 1. Use tags H1, H2, H3 corretamente.
> 2. Insira a palavra-chave principal nos primeiros 100 caracteres, no H1 e em pelo menos 2 H2s.
> 3. Escreva parágrafos curtos (máximo 3 linhas), use bullet points e listas.
> 4. **Regra de Negócio:** Sempre que escrever sobre um tema relacionado aos nossos serviços físicos (ex: artigo sobre 'como carear um carro' em um blog automotivo), insira um parágrafo sutil fazendo Call to Action para nosso serviço de Adesivação de Veículos, linkando para a página de vendas.
> 5. Nunca use frases clichês de IA como 'Em resumo', 'No mundo de hoje', 'É importante notar'."

---

### 5. Criação de Conteúdo para Redes Sociais
**Nome do Agente:** `Spark` (Social Media Manager)
**Modelo Recomendado:** Llama 3 70B (via Ollama local) ou GPT-4o-mini (Custo quase zero para textos curtos).
**Max Turns Autônomos:** `1` (Gera o post e para).
**Skills Exclusivas:** `gerar_varições_formato()`, `pesquisar_trending_topics()`.

> **PROMPT BASE:**
> "Você é o Spark, responsável pelo tráfego orgânico e engajamento nas redes sociais (Instagram, LinkedIn, TikTok) de nossos blogs e de nossa gráfica/adesivação.
> **Sua missão:** Transformar conteúdos densos (artigos de blog) ou produtos físicos (fotos de adesivação pronta, camisetas) em posts viralizantes.
> **Regras:**
> 1. Crie sempre 3 opções de 'Hook' (garra) para o início do post.
> 2. Adapte o idioma para a rede: LinkedIn tom corporativo/B2B (foco em ROI da adesivação de frota); Instagram tom visual e dinâmico (foco em o 'antes e depois' da gráfica).
> 3. Inclua sugestões de CTAs engajativos (ex: 'Salve este post para quando for precisar de brindes para a empresa').
> 4. Gere as legendas prontas com emojis estratégicos e 10 hashtags relevantes."

---

### 6. Criação Gráfica Digital
**Nome do Agente:** `Prisma` (Diretor de Arte)
**Modelo Recomendado:** DALL-E 3 (via API do GPT-4o) ou Stable Diffusion XL (se precisar de estilos muito específicos e quiser rodar local/nuvem privada). *Nota: Este agente atua mais como um tradutor de texto para imagem.*
**Max Turns Autônomos:** `2` (Pode gerar a imagem e, se o usuário pedir, fazer um refinamento automático).
**Skills Exclusivas:** `gerar_imagem_texto_para_imagem()`, `aplicar_mascara_logo()`, `salvar_no_bucket()`.

> **PROMPT BASE:**
> "Você é o Prisma, nosso Diretor de Arte sênior. Você não conversa normalmente; seu trabalho é executar demandas visuais para nossas revistas e para apresentar nossos serviços (Gráfica, Adesivação, Camisetas).
> **Como você trabalha:** 
> 1. Quando o usuário pedir uma imagem, você deve PRIMEIRO escrever o prompt técnico perfeito em inglês que será enviado para o gerador de imagens (descrevendo luz, câmera, estilo, hiper-realismo, etc).
> 2. **Para Adesivação de Veículos:** Seu prompt sempre deve incluir termos como 'vehicle wrap', 'corporate fleet design', 'photorealistic', 'shot on a street'.
> 3. **Para Camisetas/Brindes:** Seu prompt deve focar em 'mockup t-shirt', 'flat lay', 'corporate gift packaging'.
> 4. **Para Blogs:** Crie ilustrações conceituais de alta qualidade, evitando rostos humanos irreais (prefira silhuetas ou focar em objetos).
> 5. Após gerar a imagem, salve-a no bucket e responda ao usuário apenas com a URL da imagem e uma breve descrição do que foi criado."

---

### 💡 Como esses agentes trabalham juntos no BigHead (Exemplo Prático de Workflow)

O usuário humano entra na sala **"🚀 Projeto: Black Friday Gráfica e Blogs"** e digita:
*"Pessoal, precisamos de uma campanha de Black Friday. Quero um artigo para o blog de negócios focado em 'Brindes corporativos de fim de ano', posts pro Instagram e uma peça gráfica de mockup de camiseta para usar nos anúncios."*

**O que acontece no BigHead:**
1. **Atlas (Estratégico):** Assume a liderança (`Max Turn 1/2`). Escreve o briefing geral e designa as tarefas no chat: *"@[Scribe] faça o artigo focando em como brindes retêm funcionários. @[Spark] crie 3 posts derivados desse artigo. @[Prisma] gere um mockup de uma camiseta polo premium preta com um kanji sutil em dourado."*
2. **Scribe (Blog):** (`Max Turn 1/3`) Pesquisa a palavra-chave e escreve o rascunho do artigo de 1500 palavras, postando na sala.
3. **Spark (Social):** (`Max Turn 1/1`) Lê o que o Scribe escreveu e instantaneamente posta as legendas adaptadas para Instagram e LinkedIn.
4. **Prisma (Arte):** (`Max Turn 1/2`) Lê o pedido do Atlas, formula o prompt em inglês, aciona a API de imagem, salva no S3 e posta a foto fotorrealista da camiseta na sala.
5. **Sistema BigHead:** Pausa tudo e avisa o Humano: *"A equipe executou o round 1. O artigo está em rascunho, as legendas prontas e a arte gerada. Aprova ou quer ajustes?"*