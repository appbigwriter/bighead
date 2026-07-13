export type TaskStatus = "new" | "triaged" | "in_progress" | "waiting_tool" | "waiting_human" | "ready_for_review" | "approved" | "done" | "failed" | "canceled";

const transitions: Record<TaskStatus, readonly TaskStatus[]> = {
  new: ["triaged", "canceled"],
  triaged: ["in_progress", "waiting_human", "canceled"],
  in_progress: ["waiting_tool", "waiting_human", "ready_for_review", "failed", "canceled"],
  waiting_tool: ["in_progress", "failed", "canceled"],
  waiting_human: ["in_progress", "ready_for_review", "canceled"],
  ready_for_review: ["approved", "in_progress", "canceled"],
  approved: ["done", "in_progress"],
  failed: ["in_progress", "canceled"],
  done: [],
  canceled: []
};

export function isTaskStatus(value: string | undefined): value is TaskStatus {
  return Boolean(value && value in transitions);
}

export function allowedTaskTransitions(status: string | undefined): readonly TaskStatus[] {
  return isTaskStatus(status) ? transitions[status] : [];
}
