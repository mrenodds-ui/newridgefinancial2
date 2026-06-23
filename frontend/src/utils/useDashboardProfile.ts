import { useState } from "react";

export function useDashboardProfile() {
  const [profile, setProfile] = useState(() => {
    const saved = localStorage.getItem("dashboardProfile");
    return saved || "default";
  });
  function switchProfile(newProfile: string) {
    setProfile(newProfile);
    localStorage.setItem("dashboardProfile", newProfile);
  }
  return { profile, switchProfile };
}

export function getProfiledKey(key: string, profile: string) {
  return `${profile}::${key}`;
}
