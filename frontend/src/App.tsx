import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { ConfigProvider, Notification, Spin } from "@arco-design/web-react";
import zhCN from "@arco-design/web-react/es/locale/zh-CN";
import { useAuthStore } from "@/stores/auth";
import { useAppStore } from "@/stores/app";
import AppLayout from "@/components/AppLayout";
import LoginPage from "@/pages/LoginPage";
import DashboardPage from "@/pages/DashboardPage";
import PracticePage from "@/pages/PracticePage";
import ChatPage from "@/pages/ChatPage";
import WrongBookPage from "@/pages/WrongBookPage";

// 全局轻提示统一走 Arco Notification / Toast，严禁原生 alert / confirm
Notification.config({ duration: 3000 });

export default function App() {
  const { user, ready, init } = useAuthStore();
  const theme = useAppStore((state) => state.theme);

  useEffect(() => {
    void init();
  }, [init]);

  // 深浅色主题：根节点驱动自有设计 Token，body 属性驱动 Arco 组件库暗色样式
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.body.setAttribute("arco-theme", theme);
  }, [theme]);

  if (!ready) {
    return (
      <div
        style={{
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Spin size={32} />
      </div>
    );
  }

  return (
    <ConfigProvider locale={zhCN}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={user ? <AppLayout /> : <Navigate to="/login" replace />}
        >
          <Route index element={<DashboardPage />} />
          <Route path="practice" element={<PracticePage />} />
          <Route path="wrong-book" element={<WrongBookPage />} />
          <Route path="chat" element={<ChatPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ConfigProvider>
  );
}
