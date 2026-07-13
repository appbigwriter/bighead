export const MUTATION_START_EVENT = "bighead:mutation-start";
export const MUTATION_END_EVENT = "bighead:mutation-end";

export type MutationEndDetail = { refresh: boolean };

type Timer = ReturnType<typeof setTimeout>;

let workspaceMutationDepth = 0;

export function hasActiveWorkspaceMutation() {
  return workspaceMutationDepth > 0;
}

export function createMutationRefreshCoordinator(options: {
  refresh: () => void;
  setTimer?: (callback: () => void, delay: number) => Timer;
  clearTimer?: (timer: Timer) => void;
  isBlocked?: () => boolean;
}) {
  const { refresh, setTimer = setTimeout, clearTimer = clearTimeout, isBlocked = () => false } = options;
  let mutationDepth = 0;
  let refreshQueued = false;
  let timer: Timer | undefined;
  let disposed = false;

  const flush = () => {
    if (disposed || mutationDepth > 0 || isBlocked() || !refreshQueued || timer) return;
    timer = setTimer(() => {
      timer = undefined;
      if (disposed) return;
      if (mutationDepth > 0 || isBlocked()) {
        refreshQueued = true;
        return;
      }
      refreshQueued = false;
      refresh();
    }, 0);
  };

  return {
    begin() {
      if (!disposed) mutationDepth += 1;
    },
    request() {
      if (disposed) return;
      refreshQueued = true;
      flush();
    },
    end(forceRefresh = false) {
      if (disposed) return;
      mutationDepth = Math.max(0, mutationDepth - 1);
      refreshQueued ||= forceRefresh;
      flush();
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      if (timer) clearTimer(timer);
    }
  };
}

export function beginWorkspaceMutation() {
  workspaceMutationDepth += 1;
  window.dispatchEvent(new Event(MUTATION_START_EVENT));
}

export function endWorkspaceMutation(refresh: boolean) {
  workspaceMutationDepth = Math.max(0, workspaceMutationDepth - 1);
  const event = new CustomEvent<MutationEndDetail>(MUTATION_END_EVENT, {
    cancelable: true,
    detail: { refresh }
  });
  const handled = !window.dispatchEvent(event);
  return handled;
}
