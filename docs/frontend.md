# 前端设计说明书

> 项目：智能巡检机器人二维仿真系统 V1.0（标准版）
> 日期：2026-10-23
> 版本：V1.0

## 1. 设计目标

本阶段交付“纯前端独立可运行”的完整仿真系统：地图、机器人运动、A* 寻路、虚拟传感器、规则异常检测全部在浏览器内完成。部署到静态托管后，手机浏览器打开网址即可体验全部功能；下一阶段接入 FastAPI 后端时，只需替换数据服务层实现，界面代码无需改动。

## 2. 技术栈

- Vue 3（组合式 API）
- Vite（构建工具）
- Tailwind CSS v3（原子化样式）
- 原生 Canvas（地图渲染、温度曲线）
- Vitest + jsdom（单元测试）
- Playwright（自动化截图）

## 3. 目录结构

```
frontend/
├── src/
│   ├── services/           # 数据服务层（核心抽象）
│   │   ├── robotService.js     # RobotService 统一接口
│   │   ├── simulatedService.js # 本地仿真器实现
│   │   ├── astar.js            # 前端临时 A* 实现
│   │   └── index.js
│   ├── components/         # Vue 单文件组件
│   │   ├── MapCanvas.vue
│   │   ├── ControlPanel.vue
│   │   ├── Joystick.vue
│   │   ├── StatusDashboard.vue
│   │   ├── AlertList.vue
│   │   ├── PlaybackBar.vue
│   │   └── ThemeToggle.vue
│   ├── App.vue
│   ├── main.js
│   └── style.css
├── scripts/
│   └── screenshots.mjs     # Playwright 截图脚本
├── tests/                  # Vitest 测试
├── package.json
├── vite.config.js
├── tailwind.config.js
└── eslint.config.js
```

## 4. 数据服务层设计

### 4.1 统一接口 `RobotService`

`src/services/robotService.js` 定义抽象类，约定所有界面组件与数据源交互的方式：

| 方法 | 说明 |
|------|------|
| `getMap()` | 获取当前地图对象 |
| `updateMap(map)` | 更新并持久化地图 |
| `move(dx, dy)` | 手动单步移动 |
| `reset()` | 复位机器人 |
| `computePath(start, goal)` | A* 路径规划调试接口 |
| `startPatrol(goals)` | 开始自动巡检 |
| `stopPatrol()` | 停止巡检 |
| `getPatrolStatus()` | 获取巡检状态 |
| `getSensors()` | 获取最新传感器数据 |
| `getAnomalies()` | 获取历史异常 |
| `onState(callback)` | 注册状态推送回调 |
| `onEvent(callback)` | 注册事件推送回调 |

### 4.2 本地仿真器 `SimulatedService`

`src/services/simulatedService.js` 继承 `RobotService`，在浏览器内完整模拟后端行为：

- **仿真循环**：每 200ms 执行一次 `_tick()`，与后端 WebSocket 推送频率一致。
- **状态帧**：通过 `onState` 推送 `{ type: 'state', data: { x, y, theta, battery, speed, mode, path, sensors: { front, left, right, temperature } } }`，字段名与后端协议逐字段一致。
- **事件帧**：通过 `onEvent` 推送 `anomaly`（低电量 / 障碍物 / 传感器异常 / 过热）和 `notice` 两类事件。
- **电量模型**：移动一格消耗 0.2%，静止每 tick 消耗 0.02%；低于 20% 自动 A* 返回充电点并进入 `charging` 模式。
- **传感器模型**：前 / 左 / 右三向射线测距，1 格 = 0.5m，量程 5m，超程返回 `null`；温度基础 35℃ 并叠加运动温升与噪声。
- **异常规则**：电量过低、温度过高、传感器读数突变、碰撞障碍物时触发异常，并写入本地列表。
- **多巡检点任务**：使用最近邻贪心算法排序，每段调用 A*，支持路径回放快照。
- **持久化**：地图保存到 `localStorage`，刷新不丢失。

### 4.3 切换后端的可替换性

下一阶段实现 `RemoteService` 时，只需让 `App.vue` 中 `const service = new SimulatedService()` 改为 `new RemoteService()`。`RemoteService` 内部调用 REST API 与 WebSocket，但对外仍提供相同的 `onState/onEvent` 回调与数据结构，因此所有组件无需修改。

## 5. 前端版 A* 说明

`src/services/astar.js` 文件头明确标注：

> 【临时实现】最终版本迁移至后端 Python 模块，函数签名与返回结构保持一致。

当前实现特点：

- 四方向邻域移动，每格代价为 1。
- 使用曼哈顿距离作为启发函数。
- 返回 `{ path, visited_count, cost }`，与后端 `/api/v1/path` 调试接口契约一致。
- 时间复杂度为 O(节点数 log 节点数)，足以支撑本阶段前端演示。

## 6. 界面组件说明

| 组件 | 职责 |
|------|------|
| `MapCanvas.vue` | 栅格地图、机器人、路径、轨迹的 Canvas 渲染；支持滚轮缩放、拖拽平移、悬停高亮、障碍编辑、巡检点设置 |
| `ControlPanel.vue` | 手动方向控制、编辑模式切换、巡检启停与巡检点列表 |
| `Joystick.vue` | 移动端虚拟摇杆，持续按住时以 200ms 间隔发送方向指令 |
| `StatusDashboard.vue` | 坐标、朝向、电量、速度、模式、三向距离仪表、最近 60 秒温度折线 |
| `AlertList.vue` | 异常事件时间线，支持清空与导出 JSON |
| `PlaybackBar.vue` | 巡检完成后拖动时间轴回放轨迹 |
| `ThemeToggle.vue` | 浅色 / 深色模式切换，状态持久化到 `localStorage` |
| `App.vue` | 布局编排、响应式适配、键盘监听、Toast 弹窗、数据服务层接入 |

## 7. 响应式布局

- **桌面端（≥768px）**：左侧地图占剩余空间，右侧固定 400px 面板，纵向滚动。
- **移动端（<768px）**：地图全屏，底部抽屉折叠控制面板；点击右下角浮动按钮展开，内置虚拟摇杆。

## 8. 本地持久化

- 地图：`localStorage` 键 `irm_map_v1`，在 `updateMap()` 时自动保存，初始化时自动加载。
- 主题：`localStorage` 键 `irm_settings_v1`，保存深色模式偏好。

## 9. 测试与验证

- 单元测试位于 `src/services/__tests__/`，覆盖 A* 算法与 `SimulatedService` 的核心接口。
- 运行 `npm test` 执行 Vitest。
- 运行 `npm run lint` 执行 ESLint。
- 运行 `npm run build` 生成 `dist/`，产物无任何外部网络请求依赖。

## 10. 部署说明

本阶段产物为纯静态文件，构建后 `frontend/dist/` 可直接部署到任意静态托管平台。

### GitHub Pages（推荐）

1. 在 GitHub 创建仓库并关联本地工程。
2. 运行 `npm run deploy`，脚本会自动构建并推送到 `gh-pages` 分支。
3. 在仓库 Settings > Pages 中启用 `gh-pages` 分支。
4. 访问 `https://<用户名>.github.io/<仓库名>/`。

### Vercel / Netlify / Cloudflare Pages

导入仓库后设置 Framework Preset 为 `Vite`，Build Command 为 `npm run build`，Output Directory 为 `dist`，即可自动部署。

> 注意：测试阶段使用的临时托管链接仅用于功能验证，正式展示请使用自己的仓库或域名。
