// Locale-aware formatters. Defaults to en-IN (Bengaluru/Mumbai context).

const INR_FORMATTER = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 2,
});

const PCT_FORMATTER = new Intl.NumberFormat("en-IN", {
  style: "percent",
  maximumFractionDigits: 1,
});

const COMPACT_FORMATTER = new Intl.NumberFormat("en-IN", {
  notation: "compact",
  maximumFractionDigits: 1,
});

const DECIMAL_FORMATTER = new Intl.NumberFormat("en-IN", {
  maximumFractionDigits: 2,
});

export const fmt = {
  inr(value: number): string {
    return INR_FORMATTER.format(value);
  },
  pct(value: number): string {
    return PCT_FORMATTER.format(value);
  },
  compact(value: number): string {
    return COMPACT_FORMATTER.format(value);
  },
  decimal(value: number, fractionDigits = 2): string {
    if (fractionDigits === 2) return DECIMAL_FORMATTER.format(value);
    return new Intl.NumberFormat("en-IN", { maximumFractionDigits: fractionDigits }).format(value);
  },
  durationMs(ms: number): string {
    if (ms < 1) return "<1ms";
    if (ms < 1000) return `${Math.round(ms)}ms`;
    if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60_000).toFixed(1)}m`;
  },
  relativeTime(iso: string, now = Date.now()): string {
    const ts = Date.parse(iso);
    if (!Number.isFinite(ts)) return iso;
    const diff = (ts - now) / 1000;
    const abs = Math.abs(diff);
    const rtf = new Intl.RelativeTimeFormat("en-IN", { numeric: "auto" });
    if (abs < 60) return rtf.format(Math.round(diff), "second");
    if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
    if (abs < 86_400) return rtf.format(Math.round(diff / 3600), "hour");
    return rtf.format(Math.round(diff / 86_400), "day");
  },
  shortId(id: string, len = 8): string {
    return id.slice(0, len);
  },
};
