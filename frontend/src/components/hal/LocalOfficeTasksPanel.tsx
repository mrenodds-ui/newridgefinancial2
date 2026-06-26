import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  createOfficeManagerTask,
  fetchOfficeManagerTaskMetrics,
  fetchOfficeManagerTasks,
  updateOfficeManagerTask,
  type OfficeManagerTaskUpdateRequest,
} from "../../api/client";
import type {
  OfficeManagerTaskCategory,
  OfficeManagerTaskPriority,
  OfficeManagerTaskStatus,
} from "../../api/schemas";
import { OFFICE_MANAGER_SAFETY_LABELS, SafetyLabelStrip } from "./SafetyLabelStrip";

const TASK_TEMPLATES: { title: string; category: OfficeManagerTaskCategory }[] = [
  { title: "Call patient about missing form", category: "patient_prep" },
  { title: "Verify insurance information", category: "patient_prep" },
  { title: "Request radiograph for claim review", category: "documentation" },
  { title: "Review denial and prepare local draft", category: "claim" },
  { title: "Schedule treatment follow-up", category: "treatment_plan" },
  { title: "Check missing consent/form", category: "compliance" },
  { title: "Follow up with vendor on software issue", category: "vendor" },
];

export function LocalOfficeTasksPanel() {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<OfficeManagerTaskCategory>("other");
  const [priority, setPriority] = useState<OfficeManagerTaskPriority>("normal");
  const [assignedTo, setAssignedTo] = useState("");

  const tasksQuery = useQuery({
    queryKey: ["office-manager-tasks"],
    queryFn: () => fetchOfficeManagerTasks({ limit: 20 }),
  });
  const metricsQuery = useQuery({
    queryKey: ["office-manager-task-metrics"],
    queryFn: fetchOfficeManagerTaskMetrics,
  });

  const createMutation = useMutation({
    mutationFn: createOfficeManagerTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["office-manager-tasks"] });
      queryClient.invalidateQueries({ queryKey: ["office-manager-task-metrics"] });
      queryClient.invalidateQueries({ queryKey: ["office-manager-attention"] });
      setTitle("");
      setDescription("");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ taskId, status }: { taskId: string; status: OfficeManagerTaskStatus }) =>
      updateOfficeManagerTask(taskId, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["office-manager-tasks"] });
      queryClient.invalidateQueries({ queryKey: ["office-manager-task-metrics"] });
      queryClient.invalidateQueries({ queryKey: ["office-manager-attention"] });
    },
  });

  const canCreate = title.trim().length >= 3 && !createMutation.isPending;

  return (
    <section className="hal-workstation-card" aria-labelledby="hal-local-tasks-title">
      <div className="hal-workstation-card__header">
        <p className="eyebrow">Local office tasks</p>
        <h2 id="hal-local-tasks-title">Internal tasks in this app only</h2>
        <p>
          Create local office tasks for staff follow-up. No SoftDent writeback, no payer contact, and no external
          delivery.
        </p>
      </div>
      <SafetyLabelStrip labels={["Local only", "not_submitted", "Not written to SoftDent", "No external delivery"]} />
      {metricsQuery.data ? (
        <p>
          Open: {metricsQuery.data.open_count + metricsQuery.data.in_progress_count + metricsQuery.data.blocked_count} ·
          Urgent open: {metricsQuery.data.urgent_open_count}
        </p>
      ) : null}
      <div className="hal-draft-form">
        <label>
          Task title
          <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Review denial packet" />
        </label>
        <label>
          Description
          <textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={2} />
        </label>
        <label>
          Category
          <select value={category} onChange={(event) => setCategory(event.target.value as OfficeManagerTaskCategory)}>
            <option value="claim">Claim</option>
            <option value="patient_prep">Patient prep</option>
            <option value="documentation">Documentation</option>
            <option value="treatment_plan">Treatment plan</option>
            <option value="hygiene_recall">Hygiene / recall</option>
            <option value="compliance">Compliance</option>
            <option value="vendor">Vendor</option>
            <option value="report">Report</option>
            <option value="other">Other</option>
          </select>
        </label>
        <label>
          Priority
          <select value={priority} onChange={(event) => setPriority(event.target.value as OfficeManagerTaskPriority)}>
            <option value="low">Low</option>
            <option value="normal">Normal</option>
            <option value="high">High</option>
            <option value="urgent">Urgent</option>
          </select>
        </label>
        <label>
          Assigned to
          <input value={assignedTo} onChange={(event) => setAssignedTo(event.target.value)} placeholder="Front desk lead" />
        </label>
        <div className="hal-template-buttons">
          {TASK_TEMPLATES.map((template) => (
            <button
              key={template.title}
              type="button"
              className="refresh-button"
              onClick={() => {
                setTitle(template.title);
                setCategory(template.category);
              }}
            >
              Use: {template.title}
            </button>
          ))}
        </div>
        <button
          type="button"
          className="refresh-button"
          disabled={!canCreate}
          onClick={() =>
            createMutation.mutate({
              title: title.trim(),
              description: description.trim(),
              category,
              priority,
              assigned_to: assignedTo.trim() || null,
              source_refs: [],
              missing_data_codes: [],
            })
          }
        >
          {createMutation.isPending ? "Creating local task..." : "Create local task"}
        </button>
      </div>
      {createMutation.isError ? (
        <p className="hal-inline-error" role="alert">
          {createMutation.error instanceof Error ? createMutation.error.message : "Task could not be created."}
        </p>
      ) : null}
      {tasksQuery.data?.items.length ? (
        <ul className="hal-task-list">
          {tasksQuery.data.items.map((task) => (
            <li key={task.task_id} className="hal-task-list__item">
              <strong>{task.title}</strong>
              <span>
                {task.status} · {task.priority} · {task.category}
              </span>
              {task.description ? <p>{task.description}</p> : null}
              <div className="hal-template-buttons">
                {task.status !== "completed" ? (
                  <button
                    type="button"
                    className="refresh-button"
                    onClick={() => updateMutation.mutate({ taskId: task.task_id, status: "in_progress" })}
                  >
                    Mark in progress
                  </button>
                ) : null}
                {task.status !== "completed" ? (
                  <button
                    type="button"
                    className="refresh-button"
                    onClick={() => updateMutation.mutate({ taskId: task.task_id, status: "completed" })}
                  >
                    Mark completed
                  </button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p>No local office tasks yet.</p>
      )}
    </section>
  );
}
