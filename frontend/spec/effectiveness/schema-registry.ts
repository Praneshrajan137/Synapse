/**
 * Effectiveness_Harness — shared domain schema registry.
 *
 * This module is the single source of truth for the domain Zod schema
 * registry, keyed by the exact `schemaId` strings passed to
 * `http-client.parseWithSchema` and used in the firehose per-channel
 * `SCHEMAS` map (design "each schema is registered with a `schemaId`").
 *
 * It was promoted out of `spec/contract-fidelity/introspect.ts` (where it was
 * private) so that BOTH the Contract Fidelity drift suite and the
 * Effectiveness_Harness fixture factory bind fixtures and runtime validation
 * to one registry (design "A. Harness — schema registry + fixture factory";
 * Requirements 2.1, 2.2, 20.6). The drift suite re-exports these bindings, so
 * this is a move-and-re-export with no schema changes.
 */

import type { ZodTypeAny } from "zod";

import { AgentHealthResponseSchema } from "@domain/agent-health";
import { AuditListResponseSchema } from "@domain/audit-row";
import { CognitionEventSchema } from "@domain/cognition-event";
import { ConsensusDecisionSchema } from "@domain/consensus-decision";
import { DecisionEnvelopeSchema } from "@domain/decision-envelope";
import { DemandForecastSchema } from "@domain/demand-forecast";
import { DisruptionAlertSchema } from "@domain/disruption-alert";
import { EscalationMessageSchema } from "@domain/escalation";
import { FreshnessAlertSchema } from "@domain/freshness-alert";
import {
  CalibrationResponseSchema,
  EscalationAnalyticsSchema,
  SloResponseSchema,
} from "@domain/operations";
import { PricingUpdateSchema } from "@domain/pricing-update";
import { RoutePlanSchema } from "@domain/route-plan";
import { TwinDivergenceEventSchema, TwinStateSchema } from "@domain/twin-state";
import {
  DecisionDetailResponseSchema,
  LoginResponseSchema,
  OverrideApiResponseSchema,
  RefreshResponseSchema,
  SteeringResponseSchema,
  SystemPostureSchema,
  TopologyResponseSchema,
} from "@transport/synapse-api";

/** The `schemaId` string that keys a domain schema at the transport boundary. */
export type SchemaId = string;

/**
 * Every domain Zod schema the Console validates a backend payload against,
 * keyed by the `schemaId` string used at the transport boundary
 * (`http-client.parseWithSchema` / the firehose per-channel `SCHEMAS` map).
 *
 * This is the authoritative "domain schema registry": a capability
 * `hasDomainSchema` iff its `schemaId` resolves here.
 */
export const DOMAIN_SCHEMA_REGISTRY: Readonly<Record<SchemaId, ZodTypeAny>> = {
  // HTTP response schemas (schemaId === the value passed to http-client).
  AgentHealthResponse: AgentHealthResponseSchema,
  AuditListResponse: AuditListResponseSchema,
  ConsensusDecision: ConsensusDecisionSchema,
  TwinState: TwinStateSchema,
  LoginResponse: LoginResponseSchema,
  RefreshResponse: RefreshResponseSchema,
  OverrideApiResponse: OverrideApiResponseSchema,
  DecisionDetailResponse: DecisionDetailResponseSchema,
  TopologyResponse: TopologyResponseSchema,
  SystemPosture: SystemPostureSchema,
  SloResponse: SloResponseSchema,
  CalibrationResponse: CalibrationResponseSchema,
  EscalationAnalytics: EscalationAnalyticsSchema,
  SteeringResponse: SteeringResponseSchema,
  // Firehose per-channel payload schemas (schemaId === domain schema name).
  DecisionEnvelope: DecisionEnvelopeSchema,
  DisruptionAlert: DisruptionAlertSchema,
  RoutePlan: RoutePlanSchema,
  DemandForecast: DemandForecastSchema,
  TwinDivergenceEvent: TwinDivergenceEventSchema,
  FreshnessAlert: FreshnessAlertSchema,
  PricingUpdate: PricingUpdateSchema,
  EscalationMessage: EscalationMessageSchema,
  CognitionEvent: CognitionEventSchema,
};

/** The registered schema for `id`, or `undefined` when none is registered. */
export function getSchema(id: SchemaId): ZodTypeAny | undefined {
  return Object.hasOwn(DOMAIN_SCHEMA_REGISTRY, id) ? DOMAIN_SCHEMA_REGISTRY[id] : undefined;
}

/** True iff a schema is registered under `id`. */
export function hasSchema(id: SchemaId): boolean {
  return Object.hasOwn(DOMAIN_SCHEMA_REGISTRY, id);
}

/**
 * True iff a schema is registered under `schemaId`. Accepts `null` for the
 * common "capability has no `schemaId`" case (a schema-less capability).
 */
export function hasDomainSchema(schemaId: SchemaId | null): boolean {
  return schemaId !== null && hasSchema(schemaId);
}
