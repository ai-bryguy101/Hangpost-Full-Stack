import { afterEach, describe, expect, it, vi } from "vitest";

import { checkApiHealth } from "./api";

describe("checkApiHealth", () => {
  afterEach(() => vi.restoreAllMocks());

  it("reports ok when the API returns status ok", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: "ok", version: "0.1.0" }),
      }),
    );
    expect(await checkApiHealth()).toEqual({ ok: true, version: "0.1.0" });
  });

  it("reports not ok when fetch throws", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    expect(await checkApiHealth()).toEqual({ ok: false, version: null });
  });
});
