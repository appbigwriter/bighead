# Guia de Padronização Visual - NovaFacebrasil

Este documento define os padrões visuais para tipografia e cores a serem aplicados em todos os sites da empresa para garantir consistência de marca.

## 1. Tipografia

A tipografia é dividida em três categorias principais: Logo, Títulos e Corpo de Texto. Para garantir performance e consistência, utilizaremos fontes do **Google Fonts** ou integradas ao Next.js (`next/font`).

### 1.1. Fonte de Logo (Identidade Visual)
Para logotipos textuais que não utilizam imagem SVG vetorial, a fonte deve transmitir a personalidade da marca.

*   **Fonte Recomendada:** **Outfit** ou **Montserrat**.
*   **Características:** Modernas, geométricas (sans-serif), alta legibilidade e impacto em pesos maiores.
*   **Peso e Estilo:**
    *   **Bold (700)** ou **ExtraBold (800)** para a marca principal.
    *   *Letter-spacing* (espaçamento) ligeiramente ajustado (-0.02em) para um visual mais compacto e unido.

### 1.2. Títulos e Cabeçalhos (Headings)
Utilizada em `h1`, `h2`, `h3`, etc. Deve criar um contraste claro com o corpo do texto.

*   **Fonte Padrão:** **Outfit** (Substituta: *Plus Jakarta Sans*).
*   **Implementação:** Importar via `next/font/google`.
*   **Pesos:**
    *   H1: **Bold (700)**
    *   H2, H3: **SemiBold (600)**
    *   H4-H6: **Medium (500)**

### 1.3. Corpo de Texto (Body)
Utilizada em parágrafos, listas, botões e elementos de interface. Prioridade total para legibilidade.

*   **Fonte Padrão:** **Inter** (Substituta: *Geist Sans*).
*   **Implementação:** Importar via `next/font/google`.
*   **Pesos:**
    *   Texto regular: **Regular (400)**.
    *   Destaques/Links: **Medium (500)** ou **SemiBold (600)**.

---

## 2. Paleta de Cores

As cores seguem o esquema definido no `globals.css` e utilizam o Tailwind CSS v4.

### 2.1. Cores de Fundo (Backgrounds)

#### Modo Claro (Light Mode)
*   **Background Principal (`bg-background`):** `#F8FAFC` (Slate 50) ou `#FFFFFF` (White). 
    *   *Recomendação:* Usar `#F8FAFC` para evitar fadiga visual do branco puro em telas grandes, usando branco puro apenas em "cards" ou áreas de conteúdo destacado.
*   **Superfícies/Cards (`bg-card`):** `#FFFFFF` (White) com bordas sutis (`border-slate-200`) e sombras suaves.

#### Modo Escuro (Dark Mode)
*   **Background Principal (`bg-background`):** `#101622` (Dark Blue/Slate específico da marca) ou `#020617` (Slate 950).
    *   *Nota:* O tom `#101622` atual (`globals.css`) oferece uma identidade mais rica que o preto puro.
*   **Superfícies/Cards (`bg-card`):** `#1E293B` (Slate 800) ou `#151B2B` com transparecia (Glassmorphism).

### 2.2. Cores da Marca (Brand Colors)

*   **Primary (`text-primary`, `bg-primary`):** `#F97316` (Orange 500) a `#EA580C` (Orange 600).
    *   *Uso:* Botões principais, links ativos, ícones de destaque.
*   **Accent/Secondary:** `#FCD34D` (Amber 300) ou `#3B82F6` (Blue 500) para contraste complementar se necessário.

---

## 3. Instruções de Implementação Técnica

### Passo 1: Configurar Fontes no `layout.tsx`

```tsx
// app/[locale]/layout.tsx
import { Inter, Outfit } from "next/font/google";

// Configuração das fontes
const inter = Inter({ 
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit",
  display: "swap",
});

export default function RootLayout({ children }) {
  return (
    <html lang="pt-BR" className={`${inter.variable} ${outfit.variable}`}>
      <body className="font-sans antialiased bg-background text-foreground">
        {children}
      </body>
    </html>
  );
}
```

### Passo 2: Atualizar `globals.css` (Tailwind v4)

Atualize o bloco `@theme` no seu arquivo CSS global para vincular as variáveis CSS às classes utilitárias do Tailwind.

```css
@theme inline {
  /* Fontes */
  --font-sans: var(--font-inter), ui-sans-serif, system-ui, sans-serif;
  --font-heading: var(--font-outfit), ui-sans-serif, system-ui, sans-serif;
  
  /* Cores Estendidas - Mantendo consistência com o design system */
  --color-brand-primary: #F97316;
  --color-brand-dark: #101622;
}
```

### Passo 3: Utilização no Código

*   **Para Textos Gerais:** A classe `font-sans` já é padrão. Nenhuma ação extra necessária.
*   **Para Títulos:** Adicione a classe `font-heading` aos seus elementos de título.
    ```tsx
    <h1 className="font-heading text-4xl font-bold text-slate-900 dark:text-white">
      Título da Página
    </h1>
    ```
*   **Para Logos em Texto:**
    ```tsx
    <span className="font-heading font-extrabold text-2xl tracking-tight text-primary">
      NovaFacebrasil
    </span>
    ```

---

## 4. Checklist de Padronização para Novos Sites

1.  **[ ] Instalar Fontes:** Confirmar se `Inter` e `Outfit` (ou as escolhidas) estão configuradas no `layout.tsx`.
2.  **[ ] Definir Variáveis:** Garantir que o `globals.css` tenha as variáveis `--font-sans` e `--font-heading`.
3.  **[ ] Dark Mode:** Verificar se o `darkMode: 'class'` está ativo e se os componentes suportam classes `dark:`.
4.  **[ ] Contraste:** Testar textos primários em fundo claro e escuro para garantir legibilidade (taxa de contraste > 4.5:1).
