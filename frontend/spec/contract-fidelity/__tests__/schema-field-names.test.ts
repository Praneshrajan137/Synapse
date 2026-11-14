// Canary for the zod 4 field reader in ../introspect.ts.
//
// Every missing-field and over-strict drift row in run.ts is computed by `schemaFieldNames`.
// Under zod 4 the zod 3 reader found `_def.typeName` undefined on every schema and returned []
// for all of them, so the over-strict rows went empty without failing. These cases pin the
// reader's required set to the one zod's own object parse enforces, through each wrapper kind
// the registry uses, and pin the refusal for a value the reader has no rule for.

import { describe, expect, it } from "vitest";
import { z } from "zod";

import { schemaFieldNames, unwrapSchema } from "../introspect";

const base = z.object({ a: z.string(), b: z.string().optional() });

/** A value shaped like a zod schema but not built by zod, as a broken import could hand over. */
function counterfeit(value: unknown): z.core.$ZodType {
  return value as z.core.$ZodType;
}

describe("schemaFieldNames reads the fields of a zod 4 object", () => {
  it("returns only the required fields when requiredOnly is set", () => {
    expect(schemaFieldNames(base, true)).toEqual(["a"]);
    expect(schemaFieldNames(base)).toEqual(["a", "b"]);
  });

  it("reads through .optional()", () => {
    expect(schemaFieldNames(base.optional(), true)).toEqual(["a"]);
    expect(schemaFieldNames(base.optional())).toEqual(["a", "b"]);
  });

  it("reads through .default()", () => {
    const defaulted = base.default({ a: "x" });
    expect(schemaFieldNames(defaulted, true)).toEqual(["a"]);
    expect(schemaFieldNames(defaulted)).toEqual(["a", "b"]);
  });

  it("flattens both sides of an .and() intersection", () => {
    const joined = base.and(z.object({ c: z.number(), d: z.number().optional() }));
    expect(schemaFieldNames(joined, true)).toEqual(["a", "c"]);
    expect(schemaFieldNames(joined)).toEqual(["a", "b", "c", "d"]);
  });

  it("reads the object side of the pipe that .transform() and z.preprocess() build", () => {
    expect(schemaFieldNames(base.transform((value) => value), true)).toEqual(["a"]);
    expect(schemaFieldNames(z.preprocess((value) => value, base), true)).toEqual(["a"]);
  });

  it("peels stacked wrappers down to the object instance itself", () => {
    expect(unwrapSchema(base.optional().nullable())).toBe(base);
  });

  it("agrees with the parser: a defaulted field may be absent and a nullable one may not", () => {
    const schema = z.object({
      nullable: z.string().nullable(),
      defaulted: z.string().default("x"),
      optional: z.string().optional(),
    });
    expect(schemaFieldNames(schema, true)).toEqual(["nullable"]);
    expect(schema.safeParse({ nullable: null }).success).toBe(true);
    expect(schema.safeParse({}).success).toBe(false);
  });

  it("returns no fields for a kind that is compared as an open shape", () => {
    expect(schemaFieldNames(z.record(z.string(), z.number()))).toEqual([]);
    expect(schemaFieldNames(z.string())).toEqual([]);
  });
});

describe("schemaFieldNames refuses a value it has no rule for", () => {
  it("throws on a kind zod 4.6.7 does not have", () => {
    const unknownKind = counterfeit({ _zod: { def: { type: "not_a_zod_kind" } } });
    expect(() => schemaFieldNames(unknownKind)).toThrow(/kind "not_a_zod_kind"/);
  });

  it("throws when the definition names no kind", () => {
    const noKind = counterfeit({ _zod: { def: {} } });
    expect(() => schemaFieldNames(noKind, true)).toThrow(/kind "undefined"/);
  });

  it("throws when the value carries no zod definition at all", () => {
    expect(() => schemaFieldNames(counterfeit({}))).toThrow(/kind "undefined"/);
  });

  it("throws when a wrapper wraps something that is not a schema", () => {
    const hollow = counterfeit({ _zod: { def: { type: "optional", innerType: 42 } } });
    expect(() => schemaFieldNames(hollow)).toThrow(/optional\.innerType is not a zod schema/);
  });
});
