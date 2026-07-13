import { REALTIME_SUBSCRIBE_STATES, type RealtimeChannel, type RealtimePostgresChangesPayload } from "@supabase/supabase-js";

import { encodeSse, isSameSiteEventSource, isUuid, type WorkspaceRealtimeEvent } from "@/lib/realtime-protocol";
import { createClient } from "@/lib/supabase/server";
import { getWorkspaceRequestContext } from "@/lib/workspace-request-context";
import { shouldUseMockWorkspace } from "@/lib/workspace-mode";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const encoder = new TextEncoder();
const TABLES = ["messages", "tasks", "notifications"] as const;

type ChangePayload = RealtimePostgresChangesPayload<Record<string, unknown>>;

function safeEvent(table: WorkspaceRealtimeEvent["table"], operation: WorkspaceRealtimeEvent["operation"], payload: ChangePayload, sequence: number) {
  const row = payload.new as Record<string, unknown>;
  const entityId = typeof row.id === "string" ? row.id : "unknown";
  const occurredAt = typeof payload.commit_timestamp === "string" ? payload.commit_timestamp : new Date().toISOString();
  const version = Number.isInteger(row.version) && Number(row.version) >= 0 ? Number(row.version) : undefined;
  return {
    id: `${occurredAt}:${table}:${operation}:${entityId}:${sequence}`,
    table,
    operation,
    entityId,
    occurredAt,
    ...(version === undefined ? {} : { version })
  } satisfies WorkspaceRealtimeEvent;
}

export async function GET(request: Request) {
  if (shouldUseMockWorkspace()) return new Response(null, { status: 404 });
  if (!isSameSiteEventSource(request.url, request.headers.get("sec-fetch-site"), request.headers.get("origin"))) {
    return Response.json({ detail: "Cross-site realtime connection denied" }, { status: 403 });
  }

  const { tenantId } = await getWorkspaceRequestContext(request.signal);
  if (!isUuid(tenantId)) return Response.json({ detail: "Valid organization context required" }, { status: 400 });

  const supabase = await createClient();
  const { data: claims, error: claimsError } = await supabase.auth.getClaims();
  if (claimsError || !claims?.claims) return Response.json({ detail: "Invalid session" }, { status: 401 });
  const { data: sessionData, error: sessionError } = await supabase.auth.getSession();
  const session = sessionData.session;
  if (sessionError || !session?.access_token) return Response.json({ detail: "Invalid session" }, { status: 401 });

  const { data: organization, error: membershipError } = await supabase.from("organizations").select("id").eq("id", tenantId).maybeSingle();
  if (membershipError || !organization) return Response.json({ detail: "Active organization membership required" }, { status: 403 });

  await supabase.realtime.setAuth(session.access_token);
  let cleanup = () => undefined;
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      let channel: RealtimeChannel;
      let stopped = false;
      let sequence = 0;
      const timers = new Set<ReturnType<typeof setTimeout>>();
      const send = (event: string, data: unknown, id?: string) => {
        if (!stopped) controller.enqueue(encoder.encode(encodeSse(event, data, id)));
      };
      controller.enqueue(encoder.encode("retry: 2000\n\n"));
      const onChange = (table: typeof TABLES[number], operation: "INSERT" | "UPDATE") => (payload: ChangePayload) => {
        const event = safeEvent(table, operation, payload, ++sequence);
        send("workspace", event, event.id);
      };

      channel = supabase.channel(`workspace:${tenantId}:${crypto.randomUUID()}`);
      for (const table of TABLES) {
        channel = channel
          .on("postgres_changes", { event: "INSERT", schema: "public", table, filter: `organization_id=eq.${tenantId}` }, onChange(table, "INSERT"))
          .on("postgres_changes", { event: "UPDATE", schema: "public", table, filter: `organization_id=eq.${tenantId}` }, onChange(table, "UPDATE"));
      }

      cleanup = () => {
        if (stopped) return;
        stopped = true;
        timers.forEach((timer) => { clearTimeout(timer); clearInterval(timer); });
        request.signal.removeEventListener("abort", cleanup);
        void supabase.removeChannel(channel);
        try { controller.close(); } catch { /* stream already canceled */ }
      };
      request.signal.addEventListener("abort", cleanup, { once: true });

      const heartbeat = setInterval(() => {
        if (!stopped) controller.enqueue(encoder.encode(": keepalive\n\n"));
      }, 15_000);
      timers.add(heartbeat);

      const expiresAt = (session.expires_at ?? Math.floor(Date.now() / 1000) + 300) * 1000;
      const reconnectIn = Math.max(1_000, Math.min(15 * 60_000, expiresAt - Date.now() - 30_000));
      const expiry = setTimeout(cleanup, reconnectIn);
      timers.add(expiry);

      channel.subscribe((status) => {
        if (status === REALTIME_SUBSCRIBE_STATES.SUBSCRIBED) send("ready", { retry: 2_000 });
        if (status === REALTIME_SUBSCRIBE_STATES.CHANNEL_ERROR || status === REALTIME_SUBSCRIBE_STATES.TIMED_OUT || status === REALTIME_SUBSCRIBE_STATES.CLOSED) cleanup();
      });
    },
    cancel() { cleanup(); }
  });

  return new Response(stream, {
    headers: {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-cache, no-transform",
      "x-accel-buffering": "no",
      "content-encoding": "none"
    }
  });
}
