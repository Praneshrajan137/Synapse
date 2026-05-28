import { cn } from "@lib/cn";
import { useState } from "react";

// ADR-039 — visible deployed version. The two values are injected at image
// build time by .github/workflows/cd-gcp.yml:
//   VITE_BUILD_SHA  → the full git SHA the image was built from
//   VITE_BUILD_TIME → ISO-8601 UTC build timestamp
// `dev` / `unknown` indicate a local build that did not go through CD.
// Click the chip to copy the SHA — a screenshot is then enough to triage
// "why does this look stale?" without anyone touching the VM.

const BUILD_SHA = (import.meta.env.VITE_BUILD_SHA as string | undefined) ?? "dev";
const BUILD_TIME = (import.meta.env.VITE_BUILD_TIME as string | undefined) ?? "unknown";

function shortSha(sha: string): string {
  if (sha === "dev" || sha === "unknown") return sha;
  return sha.length > 7 ? sha.slice(0, 7) : sha;
}

export function BuildSHAChip() {
  const [copied, setCopied] = useState(false);
  const isPipelineBuild = BUILD_SHA !== "dev" && BUILD_SHA !== "gcp";

  const onCopy = () => {
    void navigator.clipboard.writeText(`sha=${BUILD_SHA} built=${BUILD_TIME}`).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  const title = isPipelineBuild
    ? `Deployed: ${BUILD_SHA}\nBuilt:    ${BUILD_TIME}\nClick to copy`
    : "Local build (no SHA from CD pipeline). Pipeline-built images report a real SHA.";

  return (
    <button
      type="button"
      onClick={onCopy}
      title={title}
      aria-label={`Build version ${shortSha(BUILD_SHA)} — click to copy`}
      className={cn(
        "inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 text-2xs font-mono",
        "transition-colors duration-fast ease-standard",
        "focus-visible:outline-none focus-visible:shadow-focus",
        isPipelineBuild
          ? "bg-surface-raised text-ink-muted hover:text-ink"
          : "bg-signal-warning/15 text-signal-warning hover:bg-signal-warning/25",
      )}
    >
      <span aria-hidden>#</span>
      <span>{shortSha(BUILD_SHA)}</span>
      {copied && (
        <span aria-live="polite" className="text-signal-success">
          copied
        </span>
      )}
    </button>
  );
}
