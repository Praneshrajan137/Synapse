import { describe, expect, it } from "vitest";
import { fuzzyFilter, fuzzyScore } from "../fuzzy";

describe("fuzzyScore", () => {
  it("matches subsequences and rejects non-subsequences", () => {
    expect(fuzzyScore("mc", "Mission Control")).not.toBeNull();
    expect(fuzzyScore("xyz", "Mission Control")).toBeNull();
  });

  it("empty query matches with score 0", () => {
    expect(fuzzyScore("", "anything")).toBe(0);
  });

  it("is case-insensitive", () => {
    expect(fuzzyScore("MISSION", "mission control")).not.toBeNull();
  });

  it("scores contiguous + prefix matches higher", () => {
    const contiguous = fuzzyScore("mis", "Mission Control");
    const scattered = fuzzyScore("mis", "Maximum Insight System");
    expect(contiguous).not.toBeNull();
    expect(scattered).not.toBeNull();
    expect(contiguous as number).toBeGreaterThan(scattered as number);
  });
});

describe("fuzzyFilter", () => {
  const items = ["Mission Control", "Override Cockpit", "Twin Lab", "Steering"];

  it("ranks the best match first", () => {
    const out = fuzzyFilter(items, "twn", (x) => x);
    expect(out[0]).toBe("Twin Lab");
  });

  it("returns all items in order for an empty query", () => {
    expect(fuzzyFilter(items, "", (x) => x)).toEqual(items);
  });

  it("drops non-matches", () => {
    expect(fuzzyFilter(items, "zzz", (x) => x)).toEqual([]);
  });

  it("is stable for equal scores (input order preserved)", () => {
    // 'o' is at the same index (0) in both → identical scores → input order.
    const out = fuzzyFilter(["one", "ore"], "o", (x) => x);
    expect(out).toEqual(["one", "ore"]);
  });
});
