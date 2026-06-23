import "../kpi-records.css";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";

import {
  type KpiRecord,
  type KpiRecordFormValues,
  createKpiRecord,
  deleteKpiRecord,
  kpiRecordFormSchema,
  listKpiRecords,
  updateKpiRecord,
} from "../kpiRecords";
import { queryKeys } from "../queryClient";
import { DashboardCard } from "./DashboardCard";
import { EmptyState } from "./EmptyState";
import { LoadingSpinner } from "./LoadingSpinner";

type FormState = {
  period: string;
  production: string;
  collections: string;
  overhead_percentage: string;
};

const EMPTY_FORM: FormState = {
  period: "",
  production: "",
  collections: "",
  overhead_percentage: "",
};

function toFormState(record: KpiRecord): FormState {
  return {
    period: record.period,
    production: String(record.production),
    collections: String(record.collections),
    overhead_percentage: String(record.overhead_percentage),
  };
}

function toMutationValues(form: FormState): KpiRecordFormValues {
  return {
    period: form.period,
    production: Number(form.production),
    collections: Number(form.collections),
    overhead_percentage: Number(form.overhead_percentage),
  };
}

function formatDate(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

export function LocalKpiRecordManager(): JSX.Element {
  const queryClient = useQueryClient();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    clearErrors,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormState>({
    defaultValues: EMPTY_FORM,
  });

  const recordsQuery = useQuery({
    queryKey: queryKeys.localKpiRecords,
    queryFn: listKpiRecords,
  });

  const saveMutation = useMutation({
    mutationFn: async (values: KpiRecordFormValues) => {
      if (editingId) {
        return updateKpiRecord(editingId, values);
      }

      return createKpiRecord(values);
    },
    onSuccess: async () => {
      reset(EMPTY_FORM);
      clearErrors();
      setEditingId(null);
      setSubmitError(null);
      await queryClient.invalidateQueries({
        queryKey: queryKeys.localKpiRecords,
      });
    },
    onError: (error) => {
      setSubmitError(error instanceof Error ? error.message : "Could not save the KPI record.");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteKpiRecord,
    onSuccess: async (_, deletedId) => {
      if (editingId === deletedId) {
        setEditingId(null);
        reset(EMPTY_FORM);
        clearErrors();
      }
      await queryClient.invalidateQueries({
        queryKey: queryKeys.localKpiRecords,
      });
    },
  });

  const isBusy = saveMutation.isPending || deleteMutation.isPending || isSubmitting;
  const submitLabel = editingId ? "Update record" : "Save record";
  const orderedRecords = useMemo(() => recordsQuery.data ?? [], [recordsQuery.data]);

  const clearFieldError = (field: keyof FormState): void => {
    clearErrors(field);
    setSubmitError(null);
  };

  const onSubmit = async (draft: FormState): Promise<void> => {
    const parsed = kpiRecordFormSchema.safeParse(toMutationValues(draft));

    if (!parsed.success) {
      const fieldErrors = parsed.error.flatten().fieldErrors;
      if (fieldErrors.period?.[0]) {
        setError("period", { message: fieldErrors.period[0] });
      }
      if (fieldErrors.production?.[0]) {
        setError("production", { message: fieldErrors.production[0] });
      }
      if (fieldErrors.collections?.[0]) {
        setError("collections", { message: fieldErrors.collections[0] });
      }
      if (fieldErrors.overhead_percentage?.[0]) {
        setError("overhead_percentage", {
          message: fieldErrors.overhead_percentage[0],
        });
      }
      return;
    }

    await saveMutation.mutateAsync(parsed.data);
  };

  const startEdit = (record: KpiRecord) => {
    setEditingId(record.id);
    reset(toFormState(record));
    clearErrors();
    setSubmitError(null);
  };

  return (
    <DashboardCard title="Local KPI Records" accent="green">
      <div className="kpi-records-main">
        <p className="kpi-records-desc">Save and manage monthly KPI records locally in IndexedDB. Records persist after a page refresh.</p>

        <form onSubmit={(event) => void handleSubmit(onSubmit)(event)} className="kpi-records-form" aria-label="Local KPI record form">
          <div className="kpi-records-fields">
            <label className="kpi-records-label">
              <span>Period</span>
              <input
                {...register("period", {
                  onChange: () => clearFieldError("period"),
                })}
                placeholder="2026-05"
              />
              {errors.period ? <span className="kpi-records-error">{errors.period.message}</span> : null}
            </label>

            <label className="kpi-records-label">
              <span>Production</span>
              <input
                {...register("production", {
                  onChange: () => clearFieldError("production"),
                })}
                inputMode="decimal"
                placeholder="135000"
              />
              {errors.production ? <span className="kpi-records-error">{errors.production.message}</span> : null}
            </label>

            <label className="kpi-records-label">
              <span>Collections</span>
              <input
                {...register("collections", {
                  onChange: () => clearFieldError("collections"),
                })}
                inputMode="decimal"
                placeholder="126500"
              />
              {errors.collections ? <span className="kpi-records-error">{errors.collections.message}</span> : null}
            </label>

            <label className="kpi-records-label">
              <span>Overhead %</span>
              <input
                {...register("overhead_percentage", {
                  onChange: () => clearFieldError("overhead_percentage"),
                })}
                inputMode="decimal"
                placeholder="26"
              />
              {errors.overhead_percentage ? <span className="kpi-records-error">{errors.overhead_percentage.message}</span> : null}
            </label>
          </div>

          <div className="kpi-records-actions">
            <button type="submit" disabled={isBusy}>
              {saveMutation.isPending ? "Saving..." : submitLabel}
            </button>
            {editingId ? (
              <button
                type="button"
                onClick={() => {
                  setEditingId(null);
                  reset(EMPTY_FORM);
                  clearErrors();
                  setSubmitError(null);
                }}
                disabled={isBusy}
              >
                Cancel edit
              </button>
            ) : null}
          </div>

          {submitError ? <p className="kpi-records-submit-error">{submitError}</p> : null}
        </form>

        {recordsQuery.isPending ? <LoadingSpinner label="Loading saved KPI records..." /> : null}

        {recordsQuery.error ? (
          <EmptyState
            title="Could not load local records"
            message={recordsQuery.error instanceof Error ? recordsQuery.error.message : "IndexedDB is unavailable."}
            actionLabel="Retry"
            onAction={() => void recordsQuery.refetch()}
          />
        ) : null}

        {!recordsQuery.isPending && !recordsQuery.error && orderedRecords.length === 0 ? (
          <EmptyState title="No saved KPI records" message="Add a monthly KPI record to test local persistence." />
        ) : null}

        {orderedRecords.length > 0 ? (
          <ul className="kpi-records-list">
            {orderedRecords.map((record) => (
              <li className="kpi-records-list-item" key={record.id}>
                <div className="kpi-records-list-row">
                  <div className="kpi-records-list-meta">
                    <strong>{record.period}</strong>
                    <span>Production: {record.production.toLocaleString()}</span>
                    <span>Collections: {record.collections.toLocaleString()}</span>
                    <span>Overhead: {record.overhead_percentage}%</span>
                    <span className="kpi-records-list-updated">Updated {formatDate(record.updated_at)}</span>
                  </div>

                  <div className="kpi-records-actions">
                    <button type="button" onClick={() => startEdit(record)} disabled={isBusy}>
                      Edit
                    </button>
                    <button type="button" onClick={() => void deleteMutation.mutateAsync(record.id)} disabled={isBusy}>
                      {deleteMutation.isPending ? "Deleting..." : "Delete"}
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </DashboardCard>
  );
}
