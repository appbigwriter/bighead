import { createHash, webcrypto } from "node:crypto";
import { describe, expect, it, vi } from "vitest";

import { putSignedUpload, sha256Hex } from "./signed-upload";

describe("browser signed upload", () => {
  it("calculates the checksum before metadata initiation", async () => {
    vi.stubGlobal("crypto", webcrypto);
    const bytes = new TextEncoder().encode("BigHead");
    const file = {
      size: bytes.byteLength,
      arrayBuffer: () => Promise.resolve(bytes.buffer),
    };
    expect(await sha256Hex(file)).toBe(createHash("sha256").update("BigHead").digest("hex"));
    vi.unstubAllGlobals();
  });

  it("puts bytes directly into the signed URL and maps storage failures", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 200 }));
    await expect(putSignedUpload("https://storage.example.test/signed", { "content-type": "text/plain" }, new Blob(["bytes"]), fetcher)).resolves.toBeNull();
    expect(fetcher).toHaveBeenCalledWith("https://storage.example.test/signed", expect.objectContaining({ method: "PUT" }));
    fetcher.mockResolvedValueOnce(new Response(null, { status: 503 }));
    await expect(putSignedUpload("https://storage.example.test/signed", {}, new Blob(["bytes"]), fetcher)).resolves.toMatchObject({ status: 503 });
  });
});
