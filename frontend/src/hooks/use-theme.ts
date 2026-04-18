import { useEffect, useState } from "react";

export function useTheme() {
  // 保持初始化逻辑与 index.html 一致
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem("theme") || "dark";
  });

  useEffect(() => {
    const root = window.document.documentElement;
    
    // 计算最终要应用的类名
    let resolvedTheme = theme;
    if (theme === "system") {
      resolvedTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }

    // 优化：只有在类名不存在时才添加，避免闪烁或不必要的 DOM 操作
    if (!root.classList.contains(resolvedTheme)) {
      root.classList.remove("light", "dark");
      root.classList.add(resolvedTheme);
    }
    
    localStorage.setItem("theme", theme);
  }, [theme]);

  return { theme, setTheme };
}