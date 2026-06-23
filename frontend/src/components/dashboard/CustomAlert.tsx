import React from "react";
import "./dashboard-surfaces.css";

export function CustomAlert({ message, type = "warning" }: { message: string; type?: "warning" | "info" | "success" | "error" }) {
  return <div className={`dashboard-custom-alert dashboard-custom-alert--${type}`}>{message}</div>;
}
