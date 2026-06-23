import { QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { DashboardDataProvider } from "./context/DashboardDataContext";
import { queryClient } from "./queryClient";
import "./styles/dashboard.css";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error('Root element "#root" was not found.');
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <DashboardDataProvider>
        <BrowserRouter basename="/app">
          <App />
        </BrowserRouter>
      </DashboardDataProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
