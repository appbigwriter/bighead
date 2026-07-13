import Link from "next/link";
import { Bell, BellRing, CheckCircle2, CircleAlert } from "lucide-react";

import { authenticatedApi } from "@/lib/server-api-client";

import styles from "./notifications-center.module.css";

export type NotificationFilter = "all" | "unread";

type NotificationRecord = {
  id: string;
  kind: string;
  title: string;
  body?: string;
  resourceType?: string;
  resourceId?: string;
  readAt?: string;
  createdAt?: string;
};

type NotificationEnvelope = {
  items?: unknown[];
  unreadCount?: number;
  nextCursor?: string | null;
};

const kindLabels: Record<string, string> = {
  approval: "Aprovação",
  assignment: "Atribuição",
  failure: "Falha",
  mention: "Menção",
  sla: "SLA",
  task: "Tarefa"
};

function text(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function normalizeNotification(value: unknown): NotificationRecord | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const item = value as Record<string, unknown>;
  const id = text(item.id);
  const title = text(item.title);
  if (!id || !title) return null;
  return {
    id,
    title,
    kind: text(item.kind) || "notification",
    ...(text(item.body) ? { body: text(item.body) } : {}),
    ...(text(item.resourceType ?? item.resource_type) ? { resourceType: text(item.resourceType ?? item.resource_type) } : {}),
    ...(text(item.resourceId ?? item.resource_id) ? { resourceId: text(item.resourceId ?? item.resource_id) } : {}),
    ...(text(item.readAt ?? item.read_at) ? { readAt: text(item.readAt ?? item.read_at) } : {}),
    ...(text(item.createdAt ?? item.created_at) ? { createdAt: text(item.createdAt ?? item.created_at) } : {})
  };
}

function notificationHref(item: NotificationRecord) {
  if (!item.resourceType || !item.resourceId) return null;
  const type = item.resourceType.toLowerCase();
  const id = encodeURIComponent(item.resourceId);
  if (["task", "tasks"].includes(type)) return `/tarefas/detalhe?taskId=${id}`;
  if (["approval", "approval_request", "approvals"].includes(type)) return `/governanca/aprovacao-detalhe?approvalId=${id}`;
  if (["room", "rooms"].includes(type)) return `/colaboracao/sala?roomId=${id}`;
  if (["lead", "crm_lead", "leads"].includes(type)) return `/comercial/lead-detalhe?leadId=${id}`;
  return null;
}

function timeLabel(value?: string) {
  if (!value) return "Horário indisponível";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "Horário indisponível";
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC"
  }).format(date) + " UTC";
}

export async function NotificationsCenter({
  organizationId,
  filter = "all"
}: {
  organizationId: string;
  filter?: NotificationFilter;
}) {
  try {
    const response = await authenticatedApi<NotificationEnvelope>(
      `/v1/notifications?filter=${filter}&limit=50`,
      { organizationId }
    );
    const items = (response.items ?? []).map(normalizeNotification).filter((item): item is NotificationRecord => item !== null);
    const unreadCount = typeof response.unreadCount === "number" && Number.isSafeInteger(response.unreadCount) && response.unreadCount >= 0
      ? response.unreadCount
      : null;

    return (
      <div className={styles.center} aria-labelledby="notifications-title">
        <header className={styles.header}>
          <div>
            <p className={styles.eyebrow}>Caixa de entrada</p>
            <h2 id="notifications-title">Notificações</h2>
            <p>Acompanhe decisões, atribuições e sinais que pedem sua atenção.</p>
          </div>
          <div className={styles.unread} aria-label={unreadCount === null ? "Contagem não disponível" : `${unreadCount} notificações não lidas`}>
            <BellRing aria-hidden="true" size={19} />
            <strong>{unreadCount ?? "—"}</strong>
            <span>não lidas</span>
          </div>
        </header>

        <nav aria-label="Filtrar notificações" className={styles.filters}>
          <Link aria-current={filter === "all" ? "page" : undefined} href="/operacao/notificacoes?filter=all">Todas</Link>
          <Link aria-current={filter === "unread" ? "page" : undefined} href="/operacao/notificacoes?filter=unread">Não lidas</Link>
        </nav>

        {items.length ? (
          <ol className={styles.list} aria-label="Notificações recebidas">
            {items.map((item) => {
              const href = notificationHref(item);
              const content = (
                <>
                  <span className={styles.icon} data-unread={!item.readAt}><Bell aria-hidden="true" size={18} /></span>
                  <span className={styles.content}>
                    <span className={styles.meta}>
                      <span>{kindLabels[item.kind.toLowerCase()] ?? "Atualização"}</span>
                      <time dateTime={item.createdAt}>{timeLabel(item.createdAt)}</time>
                    </span>
                    <strong>{item.title}</strong>
                    {item.body ? <span className={styles.body}>{item.body}</span> : null}
                    {!href ? <small>O contexto relacionado não está mais disponível para abertura.</small> : null}
                  </span>
                  {href ? <span className={styles.open}>Abrir</span> : null}
                </>
              );
              return <li key={item.id}>{href ? <Link className={styles.row} href={href}>{content}</Link> : <div className={styles.row}>{content}</div>}</li>;
            })}
          </ol>
        ) : (
          <div className={styles.empty}>
            <CheckCircle2 aria-hidden="true" size={24} />
            <div>
              <strong>{filter === "unread" ? "Tudo em dia" : "Nenhuma notificação"}</strong>
              <p>{filter === "unread" ? "Não há notificações pendentes de leitura." : "Novas atribuições e decisões aparecerão aqui."}</p>
            </div>
          </div>
        )}

        {response.nextCursor ? <p className={styles.limitNote}>Há mais notificações além das 50 exibidas.</p> : null}
      </div>
    );
  } catch (error) {
    const denied = typeof error === "object" && error !== null && "status" in error
      && (error as { status?: unknown }).status === 403;
    return (
      <div className={styles.center} aria-labelledby="notifications-title">
        <header className={styles.header}><div><p className={styles.eyebrow}>Caixa de entrada</p><h2 id="notifications-title">Notificações</h2></div></header>
        <div className={styles.error} role="alert">
          <CircleAlert aria-hidden="true" size={24} />
          <div>
            <strong>{denied ? "Acesso não autorizado" : "Não foi possível carregar"}</strong>
            <p>{denied ? "Seu perfil não pode visualizar estas notificações." : "Tente novamente. Nenhuma alteração foi feita."}</p>
            <Link href={denied ? "/operacao/home" : "/operacao/notificacoes"}>
              {denied ? "Voltar ao inÃ­cio" : "Tentar novamente"}
            </Link>
          </div>
        </div>
      </div>
    );
  }
}
