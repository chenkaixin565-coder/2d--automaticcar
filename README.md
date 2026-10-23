# 智能巡检机器人二维仿真系统 V1.0（标准版）

> 大学生社团培训班结业项目——前端独立运行阶段。

## 项目简介

基于 Web 的二维仿真系统：浏览器中显示由二维数组表示的栅格地图，一台虚拟巡检机器人在地图上运动。用户可手动控制机器人，也可下发自动巡检任务；机器人使用 A* 算法自动寻路、避障，虚拟传感器持续采集数据并内置规则异常检测，异常事件实时推送到前端展示。

本阶段为**纯前端独立可运行**版本：所有逻辑（地图、运动、A*、传感器、异常规则）均在浏览器内实现，部署到静态托管后手机浏览器即可完整体验。

## 技术栈

- 前端：Vue 3 + Vite + Tailwind CSS + 原生 Canvas
- 实时通信：本地 `onState/onEvent` 回调（下一阶段接入 FastAPI WebSocket）
- 构建产物：纯静态 `dist/`，无外部网络请求

## 快速开始

```bash
cd frontend
npm install
npm run dev          # 开发服务器
npm run build        # 构建产物到 dist/
npm run preview      # 预览生产构建
npm test             # 单元测试
npm run lint         # 代码检查
```

## 项目结构

```
project-root/
├── frontend/          # 前端工程
│   ├── src/services/  # 数据服务层（RobotService + SimulatedService + A*）
│   ├── src/components/# Vue 组件
│   └── ...
├── docs/              # 设计文档与截图
│   ├── frontend.md
│   └── screenshots/
├── deploy/            # Docker 与 CI/CD（后续阶段补充）
└── README.md
```

## 部署

> 注意：开发或临时预览时使用的第三方托管链接（如 `*.workbuddy.host`）仅供测试，正式上线请使用以下方式部署到自己的域名或平台。

### GitHub Pages（推荐，免费且无平台水印）

1. 在 GitHub 创建仓库，例如 `irm-frontend`，不要初始化 README。
2. 本地进入工程目录并关联远程仓库：
   ```bash
   cd frontend
   git remote add origin https://github.com/<用户名>/irm-frontend.git
   git branch -M main
   git push -u origin main
   ```
3. 执行一键部署脚本（会自动构建并推送到 `gh-pages` 分支）：
   ```bash
   npm run deploy
   ```
4. 在仓库 Settings > Pages 中选择 `gh-pages` 分支，保存。
5. 访问 `https://<用户名>.github.io/irm-frontend/`。

### Vercel

1. 在 Vercel 导入 GitHub 仓库，Framework Preset 选择 `Vite`。
2. Build Command：`npm run build`。
3. Output Directory：`dist`。
4. 点击 Deploy，获得 `*.vercel.app` 域名。

## 关键设计

- 数据服务层抽象：`src/services/robotService.js` 定义统一接口，`SimulatedService` 本地实现，下一阶段可用 `RemoteService` 替换而不改动界面。
- WebSocket 协议兼容：本地 `onState/onEvent` 推送的 JSON 结构与后端协议逐字段一致。
- 地图与设置持久化到 `localStorage`，刷新不丢。

## 文档

详见 [`docs/frontend.md`](./docs/frontend.md)。
