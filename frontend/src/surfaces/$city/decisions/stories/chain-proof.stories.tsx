/**
 * SYNAPSE Atlas Console — Storybook · ChainProof.
 *
 * Three states:
 *   - Verified.
 *   - Tampered (broken at index 1) — tagged `a11y-aaa` because the
 *     red banner is a safety-critical surface (plan §12).
 *   - Empty.
 */
import type { Meta, StoryObj } from "@storybook/react";

import { canonicalize } from "@shared/canonical-json";
import { chainHash } from "@shared/hash/sha256";

import { ChainProof } from "../components/chain-proof";
import type { AuditEntry } from "../model/audit-hash";

const meta: Meta<typeof ChainProof> = {
  title: "Decision Trace/ChainProof",
  component: ChainProof,
  parameters: { layout: "padded" },
};
export default meta;

type Story = StoryObj<typeof ChainProof>;

async function buildChain(bodies: readonly unknown[]): Promise<AuditEntry[]> {
  const out: AuditEntry[] = [];
  let prev: string | null = null;
  for (const b of bodies) {
    const hash = await chainHash(prev, canonicalize(b));
    out.push({ hash, prev, body: b });
    prev = hash;
  }
  return out;
}

// The async loader runs once at story compile-time; values become
// fixtures the args reference. Storybook 8 supports top-level await.
const verified = await buildChain([
  { phase: 1, content: "ingest" },
  { phase: 2, content: "propose" },
  { phase: 3, content: "debate" },
  { phase: 4, content: "select" },
  { phase: 5, content: "commit" },
]);

const tampered: AuditEntry[] = verified.map((e, i) =>
  i === 1 ? { ...e, body: { tampered: true, original: e.body } } : e,
);

export const Verified: Story = {
  args: { entries: verified },
};

export const Tampered: Story = {
  args: { entries: tampered },
  tags: ["a11y-aaa"],
  parameters: {
    a11y: { config: { rules: [{ id: "color-contrast-enhanced", enabled: true }] } },
  },
};

export const Empty: Story = {
  args: { entries: [] },
};
