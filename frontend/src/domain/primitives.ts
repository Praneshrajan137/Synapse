import { z } from "zod";

// Shared Zod primitives used across the domain mirror.
// Domain modules import these instead of duplicating constraints.

export const ZUuid = z.string().uuid();
export const ZIsoTimestamp = z.string().datetime({ offset: true });
export const ZConfidence = z.number().min(0).max(1);
export const ZTier = z.enum(["tier_1", "tier_2", "tier_3", "tier_4"]);
export const ZCity = z.enum(["bengaluru", "mumbai"]);
export const ZSyncStatus = z.enum(["synced", "divergent", "resync_in_progress"]);

export type Uuid = z.infer<typeof ZUuid>;
export type IsoTimestamp = z.infer<typeof ZIsoTimestamp>;
export type Tier = z.infer<typeof ZTier>;
export type City = z.infer<typeof ZCity>;
