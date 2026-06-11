import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

if (import.meta.env.VITE_PUBLIC_STATIC === "1") {
  void import("./public-styles.css");
} else {
  void import("./styles.css");
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
