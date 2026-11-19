import React, { Suspense } from "react";
import { createRoot } from "react-dom/client";
import "@xyflow/react/dist/style.css";
import "./studio.css";
import { StudioPrefsProvider } from "./lib/i18n.jsx";
import { App } from "./App.jsx";

class StudioErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="lx-page" style={{ paddingTop: 64 }}>
          <div className="lx-empty-state">
            <h2>Darstellungsfehler abgefangen · UI Display Error Caught</h2>
            <p className="lx-mono-tag" style={{ maxWidth: 640, overflowWrap: "anywhere" }}>
              {String(this.state.error?.message || this.state.error)}
            </p>
            <div className="lx-btn-row">
              <button
                type="button"
                className="lx-btn lx-btn-primary"
                onClick={() => this.setState({ error: null })}
              >
                Ansicht zurücksetzen · Retry Render
              </button>
              <button
                type="button"
                className="lx-btn"
                onClick={() => window.location.reload()}
              >
                Seite neu laden · Reload
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

const rootEl = document.getElementById("root");
if (rootEl) {
  createRoot(rootEl).render(
    <React.StrictMode>
      <StudioErrorBoundary>
        <StudioPrefsProvider>
          <Suspense fallback={<div className="lx-pane-placeholder">Loading Studio…</div>}>
            <App />
          </Suspense>
        </StudioPrefsProvider>
      </StudioErrorBoundary>
    </React.StrictMode>
  );
}
