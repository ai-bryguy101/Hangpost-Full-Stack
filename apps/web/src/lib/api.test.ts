import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, checkApiHealth, createProfile, postUserLocation } from "./api";

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

describe("postUserLocation", () => {
  afterEach(() => vi.restoreAllMocks());

  it("POSTs lat/lon/accuracy as JSON with a bearer token", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        latitude: 38.9,
        longitude: -77,
        accuracy_m: 20,
        updated_at: "2026-05-29T00:00:00Z",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const res = await postUserLocation(
      { latitude: 38.9, longitude: -77, accuracy_m: 20 },
      "tok",
    );

    expect(res.updated_at).toBe("2026-05-29T00:00:00Z");
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/user-locations");
    expect(init.method).toBe("POST");
    expect(init.headers.Authorization).toBe("Bearer tok");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body)).toEqual({
      latitude: 38.9,
      longitude: -77,
      accuracy_m: 20,
    });
  });

  it("throws a typed ApiError carrying the status on a non-2xx", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        statusText: "Unauthorized",
        text: async () => "no token",
      }),
    );
    await expect(
      postUserLocation({ latitude: 0, longitude: 0, accuracy_m: null }, "x"),
    ).rejects.toMatchObject({ name: "ApiError", status: 401 });
  });
});

describe("createProfile", () => {
  afterEach(() => vi.restoreAllMocks());

  it("POSTs the profile payload with a bearer token", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ user_id: "u1", display_name: "A", handle: "a_b" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await createProfile(
      {
        display_name: "A",
        handle: "a_b",
        age: 23,
        hometown: null,
        college: null,
        interests: ["climbing"],
        liked_topics: [],
      },
      "tok",
    );

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/profiles");
    expect(init.method).toBe("POST");
    expect(init.headers.Authorization).toBe("Bearer tok");
  });

  it("surfaces a 409 as an ApiError so callers can redirect", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        statusText: "Conflict",
        text: async () => "Profile already exists",
      }),
    );
    const err = await createProfile(
      { display_name: "A", handle: "a_b", age: null, hometown: null, college: null, interests: [], liked_topics: [] },
      "tok",
    ).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(409);
  });
});
