/// <reference types="vite/client" />

import { Component, type ErrorInfo, type ReactNode } from "react";

type ErrorBoundaryProps = {
  children: ReactNode;
  contextLabel?: string;
};

type ErrorBoundaryState = {
  hasError: boolean;
  message: string;
};

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = {
    hasError: false,
    message: "",
  };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return {
      hasError: true,
      message: error.message,
    };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    if (import.meta.env.DEV) {
      // Keep the details visible in development without exposing them to end users.
      console.error("Browser app error boundary caught an error", {
        error,
        info,
      });
    }
  }

  handleReset = (): void => {
    this.setState({ hasError: false, message: "" });
  };

  render(): ReactNode {
    const contextLabel = this.props.contextLabel?.trim();
    if (this.state.hasError) {
      return (
        <main
          style={{
            padding: 24,
            fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
          }}
        >
          <section
            role="alert"
            aria-live="assertive"
            style={{
              maxWidth: 720,
              margin: "0 auto",
              padding: 20,
              borderRadius: 18,
              border: "1px solid rgba(157, 79, 45, 0.2)",
              background: "#fff8f2",
            }}
          >
            <h1 style={{ marginTop: 0 }}>Something went wrong</h1>
            <p>
              {contextLabel
                ? `${contextLabel} hit an unexpected error. Try reloading the page or retrying the last action.`
                : "The browser app hit an unexpected error. Try reloading the page or retrying the last action."}
            </p>
            <button type="button" onClick={this.handleReset}>
              Try Again
            </button>
            {import.meta.env.DEV && this.state.message ? <pre style={{ whiteSpace: "pre-wrap" }}>{this.state.message}</pre> : null}
          </section>
        </main>
      );
    }

    return this.props.children;
  }
}
