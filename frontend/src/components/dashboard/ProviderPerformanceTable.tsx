import type { ProviderProduction } from "../../types/dashboard";

export function ProviderPerformanceTable({ data }: { data: ProviderProduction[] }) {
  return (
    <section className="dashboard-provider-performance">
      <h3 className="dashboard-section-title">Provider Performance</h3>
      <table className="dashboard-provider-table">
        <thead>
          <tr>
            <th>Provider</th>
            <th>Production</th>
            <th>Collections</th>
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr key={row.provider}>
              <td>{row.provider}</td>
              <td>
                {row.production.toLocaleString("en-US", {
                  style: "currency",
                  currency: "USD",
                })}
              </td>
              <td>
                {row.collections.toLocaleString("en-US", {
                  style: "currency",
                  currency: "USD",
                })}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
