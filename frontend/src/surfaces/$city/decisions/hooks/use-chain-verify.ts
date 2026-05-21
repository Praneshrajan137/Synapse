/**
 * SYNAPSE Atlas Console — Chain Verifier hook.
 *
 * Lifts `verifyChain` into React state. Cancellable on prop change so
 * a stale chain's verification result can't overwrite the current one.
 */
import { useEffect, useState } from "react";

import { type AuditEntry, type ChainVerification, verifyChain } from "../model/audit-hash";

const PENDING: ChainVerification = {
  valid: true,
  brokenAt: -1,
  expected: null,
  actual: null,
};

export interface UseChainVerifyResult {
  readonly result: ChainVerification;
  readonly isVerifying: boolean;
}

export function useChainVerify(entries: readonly AuditEntry[] | null): UseChainVerifyResult {
  const [result, setResult] = useState<ChainVerification>(PENDING);
  const [isVerifying, setIsVerifying] = useState(false);

  useEffect(() => {
    if (!entries) {
      setResult(PENDING);
      return;
    }
    let cancelled = false;
    setIsVerifying(true);
    void verifyChain(entries).then((r) => {
      if (cancelled) return;
      setResult(r);
      setIsVerifying(false);
    });
    return () => {
      cancelled = true;
      setIsVerifying(false);
    };
  }, [entries]);

  return { result, isVerifying };
}
