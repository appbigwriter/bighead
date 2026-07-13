import { z } from "zod";

export const problemSchema = z.object({
  type: z.string(),
  title: z.string(),
  status: z.number().int(),
  detail: z.string(),
  traceId: z.string()
});

export const taskStateSchema = z.enum([
  "new",
  "triaged",
  "in_progress",
  "waiting_tool",
  "waiting_human",
  "ready_for_review",
  "approved",
  "failed",
  "done",
  "canceled"
]);
