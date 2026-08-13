import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AppStateProvider } from "./state/AppState";
import { OptimizeProvider } from "./state/OptimizeProvider";
import { readConfigFromSearch } from "./state/urlState";
import "./styles/index.css";

const initialConfigFromUrl = readConfigFromSearch(window.location.search);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AppStateProvider initial={initialConfigFromUrl}>
        <OptimizeProvider>
          <App />
        </OptimizeProvider>
      </AppStateProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
