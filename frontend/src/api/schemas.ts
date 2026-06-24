import { z } from "zod";
import { journalDraftStatusValues } from "../utils/journalDraftStatus";
import { postingQueueEnqueueModeValues } from "../utils/postingQueueLineage";
import { postingQueueStatusValues } from "../utils/postingQueueStatus";

export const kpiItemSchema = z.object({
  period: z.string(),
  production: z.number().optional().default(0),
  collections: z.number().optional().default(0),
  overhead_percentage: z.number().optional().default(0),
});

export const kpiResponseSchema = z.object({
  items: z.array(kpiItemSchema),
});

export const healthSchema = z.object({
  status: z.enum(["ok", "degraded"]),
  service: z.string().optional().default("New Ridge Family Financial"),
});

export const authSessionSchema = z.object({
  username: z.string(),
  display_name: z.string(),
  roles: z.array(z.string()).default([]),
});

export const adminGraphPointSchema = z
  .object({
    period: z.string(),
    production: z.number().optional().default(0),
    collections: z.number().optional().default(0),
    overhead_percentage: z.number().optional(),
    overheadPercentage: z.number().optional(),
  })
  .transform((item) => ({
    period: item.period,
    production: item.production ?? 0,
    collections: item.collections ?? 0,
    overhead_percentage: item.overhead_percentage ?? item.overheadPercentage ?? 0,
  }));

export const adminSummarySchema = z.object({
  last_refresh_date: z.string().optional().default(""),
  report_pull_status: z.record(z.unknown()).default({}),
  kpis: z.array(adminGraphPointSchema).default([]),
  kpi_thresholds: z.record(z.unknown()).optional().default({}),
  priority_actions: z.array(z.string()).optional().default([]),
  priority_summary: z.string().optional().default(""),
  report_summary: z.record(z.unknown()).default({}),
  dso_summary: z.record(z.unknown()).default({}),
  claims_summary: z.record(z.unknown()).default({}),
  practice_central_delta: z.record(z.unknown()).default({}),
  softdent_insights: z.record(z.unknown()).default({}),
  owner_financial: z
    .object({
      business_date: z.string().optional().default(""),
      trend_limit: z.number().optional().default(5),
      trend_points: z.number().optional().default(0),
      available_windows: z.array(z.number()).optional().default([5, 10]),
      status_label: z.string().optional().default("Waiting for source files"),
      summary: z.string().optional().default(""),
      ebitda: z.number().optional().default(0),
      revenue: z.number().optional().default(0),
      operating_expenses: z.number().optional().default(0),
      ebitda_margin_percent: z.number().optional().default(0),
      quickbooks_rows: z.number().optional().default(0),
      softdent_rows: z.number().optional().default(0),
      quickbooks_file: z
        .object({
          name: z.string().optional().default("unknown"),
          modified_at: z.string().optional().default("unknown"),
        })
        .optional()
        .default({ name: "unknown", modified_at: "unknown" }),
      softdent_file: z
        .object({
          name: z.string().optional().default("unknown"),
          modified_at: z.string().optional().default("unknown"),
        })
        .optional()
        .default({ name: "unknown", modified_at: "unknown" }),
      trend_summary: z
        .object({
          ready_windows: z.number().optional().default(0),
          attention_windows: z.number().optional().default(0),
          average_ebitda: z.number().optional().default(0),
          average_margin_percent: z.number().optional().default(0),
        })
        .optional()
        .default({
          ready_windows: 0,
          attention_windows: 0,
          average_ebitda: 0,
          average_margin_percent: 0,
        }),
      financial_operating_areas: z
        .array(
          z.object({
            title: z.string(),
            status: z.string(),
            metric: z.string(),
            detail: z.string(),
          }),
        )
        .optional()
        .default([]),
      trend_with_deltas: z
        .array(
          z.object({
            business_date: z.string().optional().default(""),
            ebitda: z.number().optional().default(0),
            delta_vs_prior: z.number().nullable().optional().default(null),
            revenue: z.number().optional().default(0),
            operating_expenses: z.number().optional().default(0),
            quickbooks_rows: z.number().optional().default(0),
            softdent_rows: z.number().optional().default(0),
            status_label: z.string().optional().default(""),
            quickbooks_file: z
              .object({ name: z.string().optional().default("unknown") })
              .optional()
              .default({ name: "unknown" }),
            softdent_file: z
              .object({ name: z.string().optional().default("unknown") })
              .optional()
              .default({ name: "unknown" }),
          }),
        )
        .optional()
        .default([]),
    })
    .optional(),
  owner_financial_detail: z
    .object({
      section: z.string().optional().default("ar"),
      section_title: z.string().optional().default("AR aging detail"),
      alert_level: z.string().optional().default("ok"),
      priority_summary: z
        .object({
          critical_count: z.number().optional().default(0),
          warning_count: z.number().optional().default(0),
          triggered_count: z.number().optional().default(0),
        })
        .optional()
        .default({ critical_count: 0, warning_count: 0, triggered_count: 0 }),
      priority_actions: z
        .array(
          z.object({
            label: z.string().optional().default(""),
            severity: z.string().optional().default("ok"),
            gap_percent: z.number().optional().default(0),
            recommended_action: z.string().optional().default(""),
          }),
        )
        .optional()
        .default([]),
      kpi_thresholds: z
        .array(
          z.object({
            id: z.string().optional().default(""),
            label: z.string().optional().default(""),
            description: z.string().optional().default(""),
            value_percent: z.number().optional().default(0),
            threshold_percent: z.number().optional().default(0),
            comparison: z.enum(["lte", "gte"]).optional().default("lte"),
            triggered: z.boolean().optional().default(false),
            severity: z.string().optional().default("ok"),
            recommended_action: z.string().optional().default(""),
          }),
        )
        .optional()
        .default([]),
    })
    .optional(),
});

export const halStatusSchema = z.object({
  mode: z.string(),
  document_count: z.number().default(0),
  storage_path: z.string().default(""),
  vector_path: z.string().default(""),
  backend: z.string().default(""),
  embedding_provider: z.string().default(""),
  financial_sources: z
    .object({
      softdent: z
        .object({
          available: z.boolean().default(false),
          period: z.string().default(""),
          provider_count: z.number().default(0),
          live_snapshot: z
            .object({
              available: z.boolean().default(false),
              health: z.string().default("warning"),
              source_backend: z.string().default("missing"),
              source_file: z.string().default(""),
              modified_at_utc: z.string().default(""),
              excerpt: z.string().default(""),
              checked_at_utc: z.string().default(""),
              confidence_label: z.string().default("manual review"),
              review_required: z.boolean().default(true),
              review_flags: z.array(z.string()).default([]),
            })
            .default({
              available: false,
              health: "warning",
              source_backend: "missing",
              source_file: "",
              modified_at_utc: "",
              excerpt: "",
              checked_at_utc: "",
              confidence_label: "manual review",
              review_required: true,
              review_flags: [],
            }),
          live_provider_ranking: z
            .object({
              available: z.boolean().default(false),
              health: z.string().default("warning"),
              source_backend: z.string().default("missing"),
              source_file: z.string().default(""),
              modified_at_utc: z.string().default(""),
              excerpt: z.string().default(""),
              checked_at_utc: z.string().default(""),
              confidence_label: z.string().default("manual review"),
              review_required: z.boolean().default(true),
              review_flags: z.array(z.string()).default([]),
            })
            .default({
              available: false,
              health: "warning",
              source_backend: "missing",
              source_file: "",
              modified_at_utc: "",
              excerpt: "",
              checked_at_utc: "",
              confidence_label: "manual review",
              review_required: true,
              review_flags: [],
            }),
          live_payer_mix: z
            .object({
              available: z.boolean().default(false),
              health: z.string().default("warning"),
              source_backend: z.string().default("missing"),
              source_file: z.string().default(""),
              modified_at_utc: z.string().default(""),
              excerpt: z.string().default(""),
              checked_at_utc: z.string().default(""),
              confidence_label: z.string().default("manual review"),
              review_required: z.boolean().default(true),
              review_flags: z.array(z.string()).default([]),
            })
            .default({
              available: false,
              health: "warning",
              source_backend: "missing",
              source_file: "",
              modified_at_utc: "",
              excerpt: "",
              checked_at_utc: "",
              confidence_label: "manual review",
              review_required: true,
              review_flags: [],
            }),
          live_collection_delta: z
            .object({
              available: z.boolean().default(false),
              health: z.string().default("warning"),
              source_backend: z.string().default("missing"),
              source_file: z.string().default(""),
              modified_at_utc: z.string().default(""),
              excerpt: z.string().default(""),
              checked_at_utc: z.string().default(""),
              confidence_label: z.string().default("manual review"),
              review_required: z.boolean().default(true),
              review_flags: z.array(z.string()).default([]),
            })
            .default({
              available: false,
              health: "warning",
              source_backend: "missing",
              source_file: "",
              modified_at_utc: "",
              excerpt: "",
              checked_at_utc: "",
              confidence_label: "manual review",
              review_required: true,
              review_flags: [],
            }),
          live_transaction_feed: z
            .object({
              available: z.boolean().default(false),
              health: z.string().default("warning"),
              source_backend: z.string().default("missing"),
              source_file: z.string().default(""),
              modified_at_utc: z.string().default(""),
              excerpt: z.string().default(""),
              checked_at_utc: z.string().default(""),
              confidence_label: z.string().default("manual review"),
              review_required: z.boolean().default(true),
              review_flags: z.array(z.string()).default([]),
            })
            .default({
              available: false,
              health: "warning",
              source_backend: "missing",
              source_file: "",
              modified_at_utc: "",
              excerpt: "",
              checked_at_utc: "",
              confidence_label: "manual review",
              review_required: true,
              review_flags: [],
            }),
          live_claims: z
            .object({
              available: z.boolean().default(false),
              health: z.string().default("warning"),
              source_backend: z.string().default("missing"),
              source_file: z.string().default(""),
              modified_at_utc: z.string().default(""),
              excerpt: z.string().default(""),
              checked_at_utc: z.string().default(""),
              confidence_label: z.string().default("manual review"),
              review_required: z.boolean().default(true),
              review_flags: z.array(z.string()).default([]),
            })
            .default({
              available: false,
              health: "warning",
              source_backend: "missing",
              source_file: "",
              modified_at_utc: "",
              excerpt: "",
              checked_at_utc: "",
              confidence_label: "manual review",
              review_required: true,
              review_flags: [],
            }),
          live_clinical_notes: z
            .object({
              available: z.boolean().default(false),
              health: z.string().default("warning"),
              source_backend: z.string().default("missing"),
              source_file: z.string().default(""),
              modified_at_utc: z.string().default(""),
              excerpt: z.string().default(""),
              checked_at_utc: z.string().default(""),
              confidence_label: z.string().default("manual review"),
              review_required: z.boolean().default(true),
              review_flags: z.array(z.string()).default([]),
            })
            .default({
              available: false,
              health: "warning",
              source_backend: "missing",
              source_file: "",
              modified_at_utc: "",
              excerpt: "",
              checked_at_utc: "",
              confidence_label: "manual review",
              review_required: true,
              review_flags: [],
            }),
        })
        .default({
          available: false,
          period: "",
          provider_count: 0,
          live_snapshot: {
            available: false,
            health: "warning",
            source_backend: "missing",
            source_file: "",
            modified_at_utc: "",
            excerpt: "",
            checked_at_utc: "",
            confidence_label: "manual review",
            review_required: true,
            review_flags: [],
          },
          live_provider_ranking: {
            available: false,
            health: "warning",
            source_backend: "missing",
            source_file: "",
            modified_at_utc: "",
            excerpt: "",
            checked_at_utc: "",
            confidence_label: "manual review",
            review_required: true,
            review_flags: [],
          },
          live_payer_mix: {
            available: false,
            health: "warning",
            source_backend: "missing",
            source_file: "",
            modified_at_utc: "",
            excerpt: "",
            checked_at_utc: "",
            confidence_label: "manual review",
            review_required: true,
            review_flags: [],
          },
          live_collection_delta: {
            available: false,
            health: "warning",
            source_backend: "missing",
            source_file: "",
            modified_at_utc: "",
            excerpt: "",
            checked_at_utc: "",
            confidence_label: "manual review",
            review_required: true,
            review_flags: [],
          },
          live_transaction_feed: {
            available: false,
            health: "warning",
            source_backend: "missing",
            source_file: "",
            modified_at_utc: "",
            excerpt: "",
            checked_at_utc: "",
            confidence_label: "manual review",
            review_required: true,
            review_flags: [],
          },
          live_claims: {
            available: false,
            health: "warning",
            source_backend: "missing",
            source_file: "",
            modified_at_utc: "",
            excerpt: "",
            checked_at_utc: "",
            confidence_label: "manual review",
            review_required: true,
            review_flags: [],
          },
          live_clinical_notes: {
            available: false,
            health: "warning",
            source_backend: "missing",
            source_file: "",
            modified_at_utc: "",
            excerpt: "",
            checked_at_utc: "",
            confidence_label: "manual review",
            review_required: true,
            review_flags: [],
          },
        }),
      quickbooks: z
        .object({
          live_revenue: z
            .object({
              topic: z.string().default("revenue"),
              available: z.boolean().default(false),
              health: z.string().default("warning"),
              source_backend: z.string().default("unavailable"),
              source_id: z.string().default(""),
              excerpt: z.string().default(""),
              checked_at_utc: z.string().default(""),
              confidence_label: z.string().default("manual review"),
              review_required: z.boolean().default(true),
              review_flags: z.array(z.string()).default([]),
            })
            .default({
              topic: "revenue",
              available: false,
              health: "warning",
              source_backend: "unavailable",
              source_id: "",
              excerpt: "",
              checked_at_utc: "",
              confidence_label: "manual review",
              review_required: true,
              review_flags: [],
            }),
          live_expenses: z
            .object({
              topic: z.string().default("expenses"),
              available: z.boolean().default(false),
              health: z.string().default("warning"),
              source_backend: z.string().default("unavailable"),
              source_id: z.string().default(""),
              excerpt: z.string().default(""),
              checked_at_utc: z.string().default(""),
              confidence_label: z.string().default("manual review"),
              review_required: z.boolean().default(true),
              review_flags: z.array(z.string()).default([]),
            })
            .default({
              topic: "expenses",
              available: false,
              health: "warning",
              source_backend: "unavailable",
              source_id: "",
              excerpt: "",
              checked_at_utc: "",
              confidence_label: "manual review",
              review_required: true,
              review_flags: [],
            }),
          live_ar: z
            .object({
              topic: z.string().default("revenue"),
              available: z.boolean().default(false),
              health: z.string().default("warning"),
              source_backend: z.string().default("unavailable"),
              source_id: z.string().default(""),
              excerpt: z.string().default(""),
              checked_at_utc: z.string().default(""),
              confidence_label: z.string().default("manual review"),
              review_required: z.boolean().default(true),
              review_flags: z.array(z.string()).default([]),
            })
            .default({
              topic: "ar",
              available: false,
              health: "warning",
              source_backend: "unavailable",
              source_id: "",
              excerpt: "",
              checked_at_utc: "",
              confidence_label: "manual review",
              review_required: true,
              review_flags: [],
            }),
          topics: z
            .array(
              z.object({
                topic: z.string(),
                configured: z.boolean().default(false),
                query_source: z.string().default("fallback"),
                fallback_count: z.number().default(0),
              }),
            )
            .default([]),
        })
        .default({
          live_revenue: {
            topic: "revenue",
            available: false,
            health: "warning",
            source_backend: "unavailable",
            source_id: "",
            excerpt: "",
            checked_at_utc: "",
            confidence_label: "manual review",
            review_required: true,
            review_flags: [],
          },
          live_expenses: {
            topic: "expenses",
            available: false,
            health: "warning",
            source_backend: "unavailable",
            source_id: "",
            excerpt: "",
            checked_at_utc: "",
            confidence_label: "manual review",
            review_required: true,
            review_flags: [],
          },
          live_ar: {
            topic: "ar",
            available: false,
            health: "warning",
            source_backend: "unavailable",
            source_id: "",
            excerpt: "",
            checked_at_utc: "",
            confidence_label: "manual review",
            review_required: true,
            review_flags: [],
          },
          topics: [],
        }),
    })
    .default({
      softdent: {
        available: false,
        period: "",
        provider_count: 0,
        live_snapshot: {
          available: false,
          health: "warning",
          source_backend: "missing",
          source_file: "",
          modified_at_utc: "",
          excerpt: "",
          checked_at_utc: "",
          confidence_label: "manual review",
          review_required: true,
          review_flags: [],
        },
        live_provider_ranking: {
          available: false,
          health: "warning",
          source_backend: "missing",
          source_file: "",
          modified_at_utc: "",
          excerpt: "",
          checked_at_utc: "",
          confidence_label: "manual review",
          review_required: true,
          review_flags: [],
        },
        live_payer_mix: {
          available: false,
          health: "warning",
          source_backend: "missing",
          source_file: "",
          modified_at_utc: "",
          excerpt: "",
          checked_at_utc: "",
          confidence_label: "manual review",
          review_required: true,
          review_flags: [],
        },
        live_collection_delta: {
          available: false,
          health: "warning",
          source_backend: "missing",
          source_file: "",
          modified_at_utc: "",
          excerpt: "",
          checked_at_utc: "",
          confidence_label: "manual review",
          review_required: true,
          review_flags: [],
        },
        live_transaction_feed: {
          available: false,
          health: "warning",
          source_backend: "missing",
          source_file: "",
          modified_at_utc: "",
          excerpt: "",
          checked_at_utc: "",
          confidence_label: "manual review",
          review_required: true,
          review_flags: [],
        },
        live_claims: {
          available: false,
          health: "warning",
          source_backend: "missing",
          source_file: "",
          modified_at_utc: "",
          excerpt: "",
          checked_at_utc: "",
          confidence_label: "manual review",
          review_required: true,
          review_flags: [],
        },
        live_clinical_notes: {
          available: false,
          health: "warning",
          source_backend: "missing",
          source_file: "",
          modified_at_utc: "",
          excerpt: "",
          checked_at_utc: "",
          confidence_label: "manual review",
          review_required: true,
          review_flags: [],
        },
      },
      quickbooks: {
        live_revenue: {
          topic: "revenue",
          available: false,
          health: "warning",
          source_backend: "unavailable",
          source_id: "",
          excerpt: "",
          checked_at_utc: "",
          confidence_label: "manual review",
          review_required: true,
          review_flags: [],
        },
        live_expenses: {
          topic: "expenses",
          available: false,
          health: "warning",
          source_backend: "unavailable",
          source_id: "",
          excerpt: "",
          checked_at_utc: "",
          confidence_label: "manual review",
          review_required: true,
          review_flags: [],
        },
        live_ar: {
          topic: "ar",
          available: false,
          health: "warning",
          source_backend: "unavailable",
          source_id: "",
          excerpt: "",
          checked_at_utc: "",
          confidence_label: "manual review",
          review_required: true,
          review_flags: [],
        },
        topics: [],
      },
    }),
});

export const halAuditSchema = z.object({
  audit_id: z.string(),
  created_at_utc: z.string().default(""),
  actor: z.string().default(""),
  mode: z.string().default(""),
  sanitized_question: z.string().default(""),
  retrieval_ids: z.array(z.string()).default([]),
  response_summary: z.string().default(""),
});

export const halAuditListSchema = z.object({
  count: z.number().default(0),
  items: z.array(halAuditSchema).default([]),
});

export const localAccountingDocumentSchema = z.object({
  id: z.number(),
  source_path: z.string().default(""),
  source_name: z.string().default(""),
  sha256: z.string().default(""),
  processed_at_utc: z.string().default(""),
  extractor: z.string().default(""),
  document_type: z.string().default("financial_document"),
  vendor_name: z.string().nullable().optional().default(null),
  invoice_number: z.string().nullable().optional().default(null),
  document_date: z.string().nullable().optional().default(null),
  total_amount: z.number().nullable().optional().default(null),
  subtotal_amount: z.number().nullable().optional().default(null),
  tax_amount: z.number().nullable().optional().default(null),
  currency: z.string().default("USD"),
  text_preview: z.string().default(""),
  raw_text: z.string().default(""),
  correction_flags: z.array(z.string()).default([]),
  confidence_label: z.string().default("manual review"),
  review_required: z.boolean().default(false),
});

export const localAccountingDocumentListSchema = z.object({
  count: z.number().default(0),
  limit: z.number().default(20),
  document_type: z.string().nullable().optional().default(null),
  search: z.string().nullable().optional().default(null),
  review_only: z.boolean().optional().default(false),
  items: z.array(localAccountingDocumentSchema).default([]),
});

export const documentRagDocumentSchema = z.object({
  document_id: z.string().default(""),
  source_name: z.string().default(""),
  stored_path: z.string().default(""),
  mime_type: z.string().default("application/octet-stream"),
  sha256: z.string().default(""),
  uploaded_at_utc: z.string().default(""),
  uploaded_by: z.string().default(""),
  page_count: z.number().default(0),
  chunk_count: z.number().default(0),
  content_char_count: z.number().default(0),
});

export const documentRagDocumentListSchema = z.object({
  count: z.number().default(0),
  limit: z.number().default(20),
  search: z.string().nullable().optional().default(null),
  items: z.array(documentRagDocumentSchema).default([]),
});

const halSanitizationFindingSchema = z.object({
  label: z.string().default(""),
  replacement: z.string().default(""),
});

const halContextSnippetSchema = z.object({
  source_id: z.string().default(""),
  title: z.string().default(""),
  category: z.string().default(""),
  excerpt: z.string().default(""),
});

const halCapabilityTierSchema = z.object({
  tier: z.string().default(""),
  priority: z.string().default(""),
  label: z.string().default(""),
  scope: z.string().default(""),
  execution_policy: z.string().default(""),
  escalation_rule: z.string().default(""),
});

const halAccessPolicySchema = z.object({
  mode: z.string().default(""),
  auth_requirement: z.string().default(""),
  network_boundary: z.string().default(""),
  audited: z.boolean().default(true),
  workspace_root: z.string().default(""),
  activity_log_path: z.string().default(""),
  review_plan_directory: z.string().default(""),
  allowed_sources: z.array(z.string()).default([]),
  disallowed_actions: z.array(z.string()).default([]),
  capability_hierarchy: z.array(halCapabilityTierSchema).default([]),
});

export const halReviewActionSchema = z.object({
  action_id: z.string().default(""),
  action_type: z.string().default(""),
  target_device: z.string().default(""),
  target_value: z.number().default(0),
  human_review_required: z.boolean().default(true),
  status: z.string().default("pending_confirmation"),
  title: z.string().default(""),
  confirmation_message: z.string().default(""),
});

export const defaultHalVoiceProfile = {
  lane: "primary",
  label: "Primary response",
  tone: "direct and grounded",
  style_notes: [] as string[],
};

const halResponseVoiceProfileSchema = z.object({
  lane: z.string().default(defaultHalVoiceProfile.lane),
  label: z.string().default(defaultHalVoiceProfile.label),
  tone: z.string().default(defaultHalVoiceProfile.tone),
  style_notes: z.array(z.string()).default(defaultHalVoiceProfile.style_notes),
});

const halGovernanceNoteSchema = z.object({
  label: z.string().default(""),
  detail: z.string().default(""),
});

export const halAskResponseSchema = z.object({
  mode: z.string().default(""),
  answer: z.string().default(""),
  sanitized_question: z.string().default(""),
  sanitization_findings: z.array(halSanitizationFindingSchema).default([]),
  retrieved_context: z.array(halContextSnippetSchema).default([]),
  guardrails: z.array(z.string()).default([]),
  audit_id: z.string().default(""),
  access_policy: halAccessPolicySchema,
  review_actions: z.array(halReviewActionSchema).default([]),
  voice_profile: halResponseVoiceProfileSchema.default(defaultHalVoiceProfile),
  governance_notes: z.array(halGovernanceNoteSchema).default([]),
});

export const documentRagUploadResponseSchema = z.object({
  message: z.string().default(""),
  document: documentRagDocumentSchema,
});

export const documentRagAskResponseSchema = z.object({
  mode: z.string().default(""),
  answer: z.string().default(""),
  sanitized_question: z.string().default(""),
  sanitization_findings: z.array(halSanitizationFindingSchema).default([]),
  retrieved_context: z.array(halContextSnippetSchema).default([]),
  guardrails: z.array(z.string()).default([]),
  audit_id: z.string().default(""),
  document_count: z.number().default(0),
  grounded: z.boolean().default(false),
});

export const halChartPlanResponseSchema = z.object({
  mode: z.string().default(""),
  status: z.literal("pending_human_review"),
  question: z.string().default(""),
  request_json: z.record(z.unknown()).default({}),
  request_file_path: z.string().default(""),
  planned_output_path: z.string().default(""),
  review_plan_path: z.string().default(""),
  preview_summary: z.string().default(""),
  flag_for_review: z.boolean().default(false),
  review_reason: z.string().nullable().optional().default(null),
  alert_reason: z.string().nullable().optional().default(null),
  guardrails: z.array(z.string()).default([]),
  audit_id: z.string().default(""),
  access_policy: halAccessPolicySchema,
});

export const halChartPlanApprovalResponseSchema = z.object({
  mode: z.string().default(""),
  status: z.literal("approved_and_rendered"),
  review_plan_path: z.string().default(""),
  request_json: z.record(z.unknown()).default({}),
  rendered_output_path: z.string().default(""),
  flag_for_review: z.boolean().default(false),
  review_reason: z.string().nullable().optional().default(null),
  alert_reason: z.string().nullable().optional().default(null),
  guardrails: z.array(z.string()).default([]),
  audit_id: z.string().default(""),
  access_policy: halAccessPolicySchema,
});

export const halChartPlanListItemSchema = z.object({
  review_plan_path: z.string().default(""),
  created_at_utc: z.string().default(""),
  status: z.string().default("pending_human_approval"),
  question: z.string().default(""),
  title: z.string().default("HAL chart"),
  chart_type: z.string().default("bar"),
  planned_output_path: z.string().default(""),
  rendered_output_path: z.string().nullable().optional().default(null),
  audit_id: z.string().default(""),
});

export const halChartPlanListResponseSchema = z.object({
  count: z.number().default(0),
  limit: z.number().default(20),
  status: z.string().nullable().optional().default(null),
  items: z.array(halChartPlanListItemSchema).default([]),
});

export const monitorMutationExecutionResultSchema = z.object({
  status: z.enum(["executed", "rejected", "failed"]).default("failed"),
  action_type: z.string().nullable().optional().default(null),
  requested_value: z.number().nullable().optional().default(null),
  applied_value: z.number().nullable().optional().default(null),
  error: z.string().nullable().optional().default(null),
  source_backend: z.string().default("ddc_ci"),
});

export const halInsuranceNarrativeSchema = z.object({
  mode: z.string(),
  matched: z.boolean().default(false),
  narrative: z.string().default(""),
  sanitized_question: z.string().default(""),
  sanitization_findings: z.array(halSanitizationFindingSchema).default([]),
  supporting_context: z.array(halContextSnippetSchema).default([]),
  guardrails: z.array(z.string()).default([]),
  audit_id: z.string().default(""),
  access_policy: halAccessPolicySchema,
  voice_profile: halResponseVoiceProfileSchema.default(defaultHalVoiceProfile),
  governance_notes: z.array(halGovernanceNoteSchema).default([]),
});

export const halPatientDossierSchema = z.object({
  mode: z.string(),
  matched: z.boolean().default(false),
  summary: z.string().default(""),
  sanitized_question: z.string().default(""),
  sanitization_findings: z.array(halSanitizationFindingSchema).default([]),
  supporting_context: z.array(halContextSnippetSchema).default([]),
  guardrails: z.array(z.string()).default([]),
  audit_id: z.string().default(""),
  access_policy: halAccessPolicySchema,
  voice_profile: halResponseVoiceProfileSchema.default(defaultHalVoiceProfile),
  governance_notes: z.array(halGovernanceNoteSchema).default([]),
});

export const journalLineSchema = z.object({
  account_code: z.string().default(""),
  account_name: z.string().default(""),
  debit: z.number().default(0),
  credit: z.number().default(0),
  memo: z.string().nullable().optional().default(""),
});

export const journalDraftValidationSchema = z.object({
  balanced: z.boolean().default(false),
  debit_total: z.number().default(0),
  credit_total: z.number().default(0),
  open_period: z.boolean().default(false),
  account_validation_passed: z.boolean().default(false),
  issues: z.array(z.string()).default([]),
});

export const journalDraftResponseSchema = z.object({
  mode: z.string().default(""),
  summary: z.string().default(""),
  lines: z.array(journalLineSchema).default([]),
  validation: journalDraftValidationSchema,
  supporting_context: z
    .array(
      z.object({
        source_id: z.string().default(""),
        title: z.string().default(""),
        category: z.string().default(""),
        excerpt: z.string().default(""),
      }),
    )
    .default([]),
  review_required: z.boolean().default(true),
  review_plan_path: z.string().nullable().optional().default(null),
  draft_status: z.enum(journalDraftStatusValues).default("draft_only"),
  queue_id: z.string().nullable().optional().default(null),
  queue_status: z.enum(postingQueueStatusValues).nullable().optional().default(null),
  enqueue_error: z.string().nullable().optional().default(null),
  audit_id: z.string().default(""),
  access_policy: halAccessPolicySchema,
});

export const accountingPolicyAnswerResponseSchema = z.object({
  mode: z.string().default(""),
  answer: z.string().default(""),
  accounting_standard: z.string().nullable().optional().default(null),
  citations: z
    .array(
      z.object({
        source_id: z.string().default(""),
        title: z.string().default(""),
        excerpt: z.string().default(""),
      }),
    )
    .default([]),
  confidence: z.string().default("low"),
  review_required: z.boolean().default(true),
  audit_id: z.string().default(""),
  access_policy: halAccessPolicySchema,
  voice_profile: halResponseVoiceProfileSchema.default(defaultHalVoiceProfile),
  governance_notes: z.array(halGovernanceNoteSchema).default([]),
});

export const accountingPostingQueueEntrySchema = z.object({
  queue_id: z.string().default(""),
  created_at_utc: z.string().default(""),
  actor: z.string().default(""),
  target_system: z.string().default("quickbooks_desktop"),
  status: z.enum(postingQueueStatusValues).default("pending_review"),
  description: z.string().default(""),
  transaction_date: z.string().default(""),
  accounting_period: z.string().default(""),
  amount: z.number().default(0),
  transaction_type: z.string().nullable().optional().default(null),
  source_audit_id: z.string().default(""),
  enqueue_mode: z.enum(postingQueueEnqueueModeValues).nullable().optional().default(null),
  lines: z.array(journalLineSchema).default([]),
  validation: journalDraftValidationSchema,
  reviewer_actor: z.string().nullable().optional().default(null),
  reviewed_at_utc: z.string().nullable().optional().default(null),
  review_note: z.string().nullable().optional().default(null),
  review_required: z.boolean().default(true),
  review_plan_path: z.string().nullable().optional().default(null),
  audit_id: z.string().nullable().optional().default(null),
});

export const accountingPostingQueueActivitySchema = z.object({
  queue_id: z.string().default(""),
  created_at_utc: z.string().default(""),
  actor: z.string().default(""),
  target_system: z.string().default("quickbooks_desktop"),
  status: z.enum(postingQueueStatusValues).default("pending_review"),
  description: z.string().default(""),
  transaction_date: z.string().default(""),
  accounting_period: z.string().default(""),
  amount: z.number().default(0),
  transaction_type: z.string().nullable().optional().default(null),
  source_audit_id: z.string().default(""),
  enqueue_mode: z.enum(postingQueueEnqueueModeValues).nullable().optional().default(null),
  reviewer_actor: z.string().nullable().optional().default(null),
  reviewed_at_utc: z.string().nullable().optional().default(null),
  review_note: z.string().nullable().optional().default(null),
  review_required: z.boolean().default(true),
});

export const accountingPostingQueueListSchema = z.object({
  count: z.number().default(0),
  total_count: z.number().default(0),
  limit: z.number().default(10),
  cursor: z.string().nullable().optional().default(null),
  next_cursor: z.string().nullable().optional().default(null),
  range_start: z.number().default(0),
  range_end: z.number().default(0),
  status: z.enum(postingQueueStatusValues).nullable().optional().default(null),
  items: z.array(accountingPostingQueueEntrySchema).default([]),
});

export const accountingPostingQueueMetricsSchema = z.object({
  total_count: z.number().default(0),
  pending_review_count: z.number().default(0),
  approved_count: z.number().default(0),
  rejected_count: z.number().default(0),
});

export const accountingPostingQueueActivityListSchema = z.object({
  count: z.number().default(0),
  limit: z.number().default(10),
  items: z.array(accountingPostingQueueActivitySchema).default([]),
});

export type KpiResponse = z.infer<typeof kpiResponseSchema>;
export type HealthResponse = z.infer<typeof healthSchema>;
export type AuthSessionResponse = z.infer<typeof authSessionSchema>;
export type AdminSummaryResponse = z.infer<typeof adminSummarySchema>;
export type HalStatusResponse = z.infer<typeof halStatusSchema>;
export type HalAuditListResponse = z.infer<typeof halAuditListSchema>;
export type LocalAccountingDocument = z.infer<typeof localAccountingDocumentSchema>;
export type LocalAccountingDocumentListResponse = z.infer<typeof localAccountingDocumentListSchema>;
export type DocumentRagDocument = z.infer<typeof documentRagDocumentSchema>;
export type DocumentRagDocumentListResponse = z.infer<typeof documentRagDocumentListSchema>;
export type DocumentRagUploadResponse = z.infer<typeof documentRagUploadResponseSchema>;
export type DocumentRagAskResponse = z.infer<typeof documentRagAskResponseSchema>;
export type HalAskResponse = z.infer<typeof halAskResponseSchema>;
export type HalChartPlanResponse = z.infer<typeof halChartPlanResponseSchema>;
export type HalChartPlanApprovalResponse = z.infer<typeof halChartPlanApprovalResponseSchema>;
export type HalChartPlanListItem = z.infer<typeof halChartPlanListItemSchema>;
export type HalChartPlanListResponse = z.infer<typeof halChartPlanListResponseSchema>;
export type HalReviewAction = z.infer<typeof halReviewActionSchema>;
export type HalInsuranceNarrativeResponse = z.infer<typeof halInsuranceNarrativeSchema>;
export type HalPatientDossierResponse = z.infer<typeof halPatientDossierSchema>;
export type MonitorMutationExecutionResult = z.infer<typeof monitorMutationExecutionResultSchema>;
export type JournalDraftResponse = z.infer<typeof journalDraftResponseSchema>;
export type AccountingPolicyAnswerResponse = z.infer<typeof accountingPolicyAnswerResponseSchema>;
export type AccountingPostingQueueEntry = z.infer<typeof accountingPostingQueueEntrySchema>;
export type AccountingPostingQueueActivity = z.infer<typeof accountingPostingQueueActivitySchema>;
export type AccountingPostingQueueListResponse = z.infer<typeof accountingPostingQueueListSchema>;
export type AccountingPostingQueueMetricsResponse = z.infer<typeof accountingPostingQueueMetricsSchema>;
export type AccountingPostingQueueActivityListResponse = z.infer<typeof accountingPostingQueueActivityListSchema>;
