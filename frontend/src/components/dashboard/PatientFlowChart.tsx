import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function PatientFlowChart({
  data,
}: {
  data: { date: string; newPatients: number; returningPatients: number }[];
}) {
  return (
    <section className="dashboard-patient-flow">
      <h3 className="dashboard-section-title">Patient Flow</h3>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} margin={{ top: 16, right: 24, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#D6B15E33" />
          <XAxis dataKey="date" stroke="#B9AA91" tick={{ fontSize: 13, fill: "#F7F0E2" }} />
          <YAxis stroke="#B9AA91" tick={{ fill: "#F7F0E2" }} />
          <Tooltip
            contentStyle={{
              background: "#18120C",
              color: "#F7F0E2",
              borderRadius: 12,
              border: "1.5px solid #D6B15E",
            }}
            labelStyle={{ color: "#D6B15E" }}
          />
          <Legend wrapperStyle={{ color: "#D6B15E" }} iconType="rect" />
          <Bar dataKey="newPatients" fill="#78A86B" name="New Patients" />
          <Bar dataKey="returningPatients" fill="#D6B15E" name="Returning Patients" />
        </BarChart>
      </ResponsiveContainer>
    </section>
  );
}
