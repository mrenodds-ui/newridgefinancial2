export function MissingDataNotice({
  title,
  detail,
  codes = [],
}: {
  title: string;
  detail: string;
  codes?: string[];
}) {
  return (
    <div className="hal-missing-data-notice" role="status">
      <strong>{title}</strong>
      <p>{detail}</p>
      {codes.length ? <p className="hal-missing-data-notice__codes">Missing data: {codes.join(", ")}</p> : null}
    </div>
  );
}
