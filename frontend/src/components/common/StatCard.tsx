export default function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div
      style={{
        background: "#fff",
        borderRadius: 8,
        padding: 20,
        minWidth: 160,
        boxShadow: "0 2px 8px #eee",
      }}
    >
      <div style={{ fontSize: 14, color: "#888", marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700 }}>{value}</div>
    </div>
  );
}
