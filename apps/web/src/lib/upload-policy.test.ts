import { describe, expect, it } from "vitest";

import { MAX_UPLOAD_BYTES, validateUploadSize } from "./upload-policy";

describe("signed upload policy", () => {
  it("accepts the API maximum and rejects the next byte", () => {
    expect(validateUploadSize(MAX_UPLOAD_BYTES)).toBeNull();
    expect(validateUploadSize(MAX_UPLOAD_BYTES + 1)).toContain("50 MiB");
  });

  it("rejects empty files before buffering", () => {
    expect(validateUploadSize(0)).toContain("Selecione");
  });
});
