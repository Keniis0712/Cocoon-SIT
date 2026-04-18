import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";

import { Toaster } from "@/components/ui/sonner";
import { router } from "@/router";
import { initializeI18n } from "./i18n";
import { useTheme } from "./hooks/use-theme";
import "@/index.css";

function AppProvider() {
  useTheme();
  return (
    <>
      <RouterProvider router={router} />
      <Toaster />
    </>
  );
}

async function bootstrap() {
  await initializeI18n();
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <AppProvider />
    </StrictMode>,
  );
}

void bootstrap();
