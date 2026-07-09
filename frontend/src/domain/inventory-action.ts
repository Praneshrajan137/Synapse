import { z } from "zod";
import { ZConfidence } from "./primitives";

// Mirror of proto/domain/inventory_action.schema.json.

export const InventoryActionSchema = z
  .object({
    store_id: z.string(),
    sku_id: z.string(),
    action_type: z.enum(["reorder", "transfer", "markdown"]),
    quantity: z.number().min(0),
    safety_stock_multiplier: z.number().min(1).max(3),
    reorder_point: z.number().min(0),
    confidence: ZConfidence,
  })
  .passthrough();

export type InventoryAction = z.infer<typeof InventoryActionSchema>;
