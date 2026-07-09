import { operatorIdentityRef } from "@lib/operator-identity";
import { useSessionStore } from "@state/session.store";
import { Badge } from "../primitives/Badge";

/**
 * Renders operator identity by VAULT-TOKEN PRESENCE only (FE-INV-019, Req 12.1,
 * STRIDE). Never displays a raw username — the audit row carries
 * `operator_token_ref` only. Renders NOTHING while unauthenticated (identity is
 * empty when there is no authenticated operator).
 */
export function OperatorIdentity() {
  const role = useSessionStore((s) => s.role);
  const tokenRef = useSessionStore((s) => s.operatorTokenRef);
  const identityRef = operatorIdentityRef(role, tokenRef);

  // Req 12.1 — operator identity renders ONLY while authenticated.
  if (role === "anonymous") return null;

  return (
    <div className="flex items-center gap-2" aria-label="Operator identity">
      <Badge tone="success">{role.toUpperCase()}</Badge>
      {identityRef && (
        <span
          className="font-mono text-2xs text-ink-muted"
          title="Vault token reference"
          aria-label="Vault token reference"
        >
          {identityRef}
        </span>
      )}
    </div>
  );
}
