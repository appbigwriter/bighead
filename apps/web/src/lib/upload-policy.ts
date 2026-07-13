export const MAX_UPLOAD_BYTES = 52_428_800;

export function validateUploadSize(size: number) {
  if (!Number.isSafeInteger(size) || size < 1) return "Selecione um arquivo.";
  if (size > MAX_UPLOAD_BYTES) return "O arquivo excede o limite de 50 MiB.";
  return null;
}
