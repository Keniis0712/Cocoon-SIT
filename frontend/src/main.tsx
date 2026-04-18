import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { router } from "@/router";
import { useTheme } from "./hooks/use-theme";
import "@/i18n";
import "@/index.css";

function AppProvider() {
  useTheme(); // 在这里调用，它会监听 theme 变化并修改 <html> 标签
  return <RouterProvider router={router} />; // 返回你的路由或主组件
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppProvider />
  </StrictMode>,
);
