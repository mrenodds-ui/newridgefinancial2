import { useState } from "react";

export type GoalType = {
  production: number;
  collections: number;
};

export function useDashboardGoals() {
  const [goals, setGoals] = useState<GoalType>(() => {
    const saved = localStorage.getItem("dashboardGoals");
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {}
    }
    return { production: 0, collections: 0 };
  });

  function saveGoals(newGoals: GoalType) {
    setGoals(newGoals);
    localStorage.setItem("dashboardGoals", JSON.stringify(newGoals));
  }

  return { goals, saveGoals };
}
