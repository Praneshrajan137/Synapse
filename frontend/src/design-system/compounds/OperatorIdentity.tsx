import { useSessionStore } from "@state/session.store";
import { Badge } from "../primitives/Badge";

/**
 * Renders operator identity by VAULT-TOKEN PRESENCE (FE-INV-019, STRIDE).
 * Never displays a raw username — the audit row carries `operator_token_ref`
 * only.
 */
export function OperatorIdentity() {
  const role = useSessionStore((s) => s.role);
  const tokenRef = useSessionStore((s) => s.operatorTokenRef);
  const authenticated = role !== "anonymous";

  return (
    <div className="flex items-center gap-2" aria-label="Operator identity">
      <Badge tone={authenticated ? "success" : "neutral"}>{role.toUpperCase()}</Badge>
      {tokenRef && (
        <span
          className="font-mono text-2xs text-ink-muted"
          title="Vault token reference"
          aria-label="Vault token reference"
        >
          {tokenRef.slice(0, 8)}
        </span>
      )}
    </div>
  );
}
