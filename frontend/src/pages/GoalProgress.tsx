import { useDashboardData } from "../context/DashboardDataContext";
import type { GoalType } from "../utils/useDashboardGoals";
import styles from "./GoalProgress.module.css";

export function GoalProgress({ goals }: { goals: GoalType }) {
  const { dashboardData } = useDashboardData();
  // Assume dashboardData is an array of records with production and collections fields
  const totalProduction = dashboardData.reduce((sum, row) => sum + (Number(row.production) || 0), 0);
  const totalCollections = dashboardData.reduce((sum, row) => sum + (Number(row.collections) || 0), 0);
  const prodPct = goals.production ? Math.min(100, (totalProduction / goals.production) * 100) : 0;
  const collPct = goals.collections ? Math.min(100, (totalCollections / goals.collections) * 100) : 0;
  return (
    <div className={styles["goal-progress-row"]}>
      <div>
        <strong>Production:</strong> ${totalProduction.toLocaleString()} / ${goals.production.toLocaleString()}
        <br />
        <progress value={prodPct} max={100} className={styles["goal-progress-bar"]} /> {prodPct.toFixed(1)}%
      </div>
      <div>
        <strong>Collections:</strong> ${totalCollections.toLocaleString()} / ${goals.collections.toLocaleString()}
        <br />
        <progress value={collPct} max={100} className={styles["goal-progress-bar"]} /> {collPct.toFixed(1)}%
      </div>
    </div>
  );
}
