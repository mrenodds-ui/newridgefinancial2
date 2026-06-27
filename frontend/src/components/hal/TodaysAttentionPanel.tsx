import { useQuery } from "@tanstack/react-query";

import { fetchOfficeManagerAttention } from "../../api/client";
import { MissingDataNotice } from "./MissingDataNotice";
import { describeMissingDataCodes } from "./missingDataLabels";
import { OFFICE_MANAGER_SAFETY_LABELS, SafetyLabelStrip } from "./SafetyLabelStrip";

export function TodaysAttentionPanel() {
  const attentionQuery = useQuery({
    queryKey: ["office-manager-attention"],
    queryFn: fetchOfficeManagerAttention,
  });

  const attention = attentionQuery.data;

  return (
    <section className="hal-workstation-card" aria-labelledby="hal-attention-title">
      <div className="hal-workstation-card__header">
        <p className="eyebrow">Today&apos;s attention</p>
        <h2 id="hal-attention-title">Office manager priorities</h2>
        <p>HAL surfaces what needs review today. All items remain local only, not submitted, and not written to SoftDent.</p>
      </div>
      <SafetyLabelStrip labels={[...OFFICE_MANAGER_SAFETY_LABELS]} />
      {attentionQuery.isPending ? <p>Loading office-manager attention...</p> : null}
      {attentionQuery.isError ? (
        <p className="hal-inline-error" role="alert">
          {attentionQuery.error instanceof Error
            ? attentionQuery.error.message
            : "Office-manager attention could not be loaded."}
        </p>
      ) : null}
      {attention ? (
        <>
          <p>{attention.summary}</p>
          <ul className="hal-attention-list">
            {attention.items.map((item) => (
              <li key={item.item_id} className={`hal-attention-item hal-attention-item--${item.severity}`}>
                <strong>{item.title}</strong>
                {item.count != null ? <span className="hal-attention-item__count">{item.count}</span> : null}
                <p>{item.detail}</p>
                {item.action_hint ? <p className="hal-attention-item__hint">{item.action_hint}</p> : null}
                {item.missing_data_codes.length ? (
                  <p className="hal-missing-data-notice__codes">{describeMissingDataCodes(item.missing_data_codes)}</p>
                ) : null}
              </li>
            ))}
          </ul>
          {attention.missing_data_codes.length ? (
            <MissingDataNotice
              title="Some office-manager lanes are limited"
              detail="HAL will not fabricate treatment-plan, recall, A/R, or vendor data without a real source."
              codes={attention.missing_data_codes}
            />
          ) : null}
        </>
      ) : null}
    </section>
  );
}
