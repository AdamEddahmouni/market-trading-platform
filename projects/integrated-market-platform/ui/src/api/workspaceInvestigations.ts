import { z } from "zod";

export const Investigation = z.object({
  workspace_id: z.string(),
  title: z.string(),
  instrument_id: z.string(),
  source_kind: z.enum(["instrument", "radar_attention"]),
  source_id: z.string().nullable(),
  opportunity_id: z.string().nullable(),
  status: z.enum(["ACTIVE", "ARCHIVED"]),
  note: z.string(),
  created_at: z.number(),
  updated_at: z.number(),
});

export const InvestigationList = z.object({ investigations: z.array(Investigation) });
