import { mutationFailure, type MutationFailure } from "./mutation-result";
import { validateUploadSize } from "./upload-policy";

type ChecksumSource = Pick<Blob, "size" | "arrayBuffer">;

export async function sha256Hex(file: ChecksumSource) {
  const sizeError = validateUploadSize(file.size);
  if (sizeError) throw new Error(sizeError);
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function putSignedUpload(
  url: string,
  headers: Record<string, string>,
  file: Blob,
  fetcher: typeof fetch = fetch
): Promise<MutationFailure | null> {
  const response = await fetcher(url, { method: "PUT", headers, body: file });
  return response.ok ? null : mutationFailure(response.status, "Falha ao enviar bytes para o Storage.");
}

export async function putSignedUploadWithRetry(
  url: string,
  headers: Record<string, string>,
  file: Blob,
  fetcher: typeof fetch = fetch,
  maxAttempts = 3
): Promise<MutationFailure | null> {
  let failure: MutationFailure | null = null;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    failure = await putSignedUpload(url, headers, file, fetcher);
    if (!failure) return null;
    const retryable = failure.status === 408 || failure.status === 429 || failure.status >= 500;
    if (!retryable) return failure;
  }
  return failure;
}
