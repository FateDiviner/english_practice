import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider } from "@arco-design/web-react";
import zhCN from "@arco-design/web-react/es/locale/zh-CN";
import "@arco-design/web-react/dist/css/arco.css";
import "./styles/global.css";
import App from "./App";

const container = document.getElementById("root");
if (!container) throw new Error("未找到 #root 挂载节点");

createRoot(container).render(
  <StrictMode>
    <BrowserRouter>
      <ConfigProvider locale={zhCN}>
        <App />
      </ConfigProvider>
    </BrowserRouter>
  </StrictMode>
);
