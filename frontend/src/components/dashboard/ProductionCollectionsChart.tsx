import { CurrencyLineChart } from "./CurrencyLineChart";

type ProductionCollectionsDatum = Record<string, string | number | null | undefined>;

export function ProductionCollectionsChart({ data }: { data: ProductionCollectionsDatum[] }) {
  return (
    <CurrencyLineChart
      data={data}
      lines={[
        { dataKey: "production", name: "Production", color: "#D6B15E" },
        { dataKey: "collections", name: "Collections", color: "#78A86B" },
      ]}
      legend={true}
    />
  );
}
