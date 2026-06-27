import { describeMissingDataCodes } from "./missingDataLabels";

export function MissingDataNotice({
  title,
  detail,
  codes = [],
}: {
  title: string;
  detail: string;
  codes?: string[];
}) {
  const friendly = describeMissingDataCodes(codes);
  return (
    <div className="hal-missing-data-notice" role="status">
      <strong>{title}</strong>
      <p>{detail}</p>
      {friendly ? <p className="hal-missing-data-notice__codes">{friendly}</p> : null}
    </div>
  );
}
