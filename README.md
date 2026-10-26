# 智能巡检机器人二维仿真系统 V2.1

> 大学生社团培训班结业项目 —— 全栈版（FastAPI 后端 + Vue 前端，单容器部署）。
> V2.0 重做了交互（规划=预览 / 遇阻=暂停询问 / 尾迹可隐藏）并修复 22 项一致性缺陷；V2.1 增加地图库、地图设计器与固定屏障，并把"清障"拆成免费的编辑擦除与扣电的机器人清障。

## 项目简介

基于 Web 的二维栅格巡检机器人仿真系统：浏览器中以二维数组渲染栅格地图，一台虚拟巡检机器人在地图上运动。用户可手动遥控，也可下发自动巡检任务；机器人用 A* 算法自动寻路避障，虚拟传感器（三向超声波、电量、温度）持续采集数据，规则与机器学习（IsolationForest）双策略做异常检测，异常事件经 WebSocket 实时推送到前端。

前端为 Vue 3 + Canvas，后端为 FastAPI（仿真引擎、A*、传感器、异常检测、巡检调度），后端同时托管前端静态页，**一个容器即可完整运行**。

## 功能特性

### V2.1 新增

- **地图库**：保存 / 载入 / 重命名 / 删除 / 导入导出 JSON；本机库（localStorage）与云端库（后端 `data/maps`）双通道
- **地图设计器**：全屏大画布，可放大缩小、自由绘制普通障碍与固定屏障、设置起点/充电点/巡检点；支持改尺寸、导出 JSON、保存后直接载入
- **固定屏障（格子值 2）**：不可穿越、机器人无法清除，只能在地图编辑时人工擦除（带二次确认）
- **清障语义拆分**：编辑期的「擦除」不耗电；只有巡检遇阻时的「清除并继续」才扣 5% 电量
- **规划预览重做**：点预览后地图自动缩放到整条路线，并弹出可拖动的预览浮层（路程/待清障/耗电），可直接「按此路线巡检」，开始后预览自动收起
- **更多详情可拖动**：移动端详情从固定抽屉改为可拖动浮窗

### V2.0 新增

- **巡检遇阻三选一**：停在障碍前一格，弹窗选择「清除并继续（-5%）/ 跳过并记入待清障 / 停止」
- **待清障记录与一键清最近**：跳过的障碍留痕（地图橙色叉号 + 面板计数），按距离由近到远清除
- **新建地图 / 重新开始**：一键新建空白图（可选尺寸）；重新开始保留尾迹，复位则清空
- **尾迹开关**：默认隐藏，可手动显示，线型统一为细虚线
- **随动平移**：取消"平移模式"，任何模式下都能拖拽/滚轮移动地图（障碍模式用右键拖拽）
- **规划 = 预览**：先看闪烁虚线与电力预算，再决定是否开始巡检
- **机器人形象重绘**：机身 + 双轮 + 传感器穹顶 + 朝向箭头 + 状态灯
- **悬停详情**：坐标、是否可通行、到达该格的理论耗电

### 基础能力

- 二维栅格地图编辑（拖动绘制障碍、设置起点与充电点）
- 手动遥控（方向键 / 屏幕摇杆）与自动巡检（最近邻 + A* 贪心路径）
- A* 自动寻路、实时避障、低电量自动返航充电
- 虚拟传感器：三向超声波测距、电量、温度，数据随仿真 tick 联动
- 异常检测：规则阈值 + IsolationForest 在线打分，双策略可切换
- WebSocket 实时状态推送与异常事件通知
- 撞障三连反馈：地图抖动动画 + 卡住弹窗提示 + 一键排障（自动清除前方障碍恢复控制）
- 机器人 2D 平滑移动：位置与朝向指数插值动画，消除格子跳变感
- 内置地图库：默认厂房 / 仓储走廊 / 障碍密集区三张预设一键切换
- 地图导入导出：JSON 格式下载与上传，导入时完整结构校验
- 自定义机器人形象：上传本地图片替换默认绘制，仅存浏览器本地
- 详情表面化：鼠标悬停任意栅格即显示坐标与类型（起点/巡检点/障碍/可通行）
- 真正的地图边界：最外环为固定边界墙——不可绘制、不可擦除、机器人不可穿越，视觉上与普通障碍明确区分（深色斜线纹理），导入地图时自动补齐
- 移动端通知不遮地图：Toast 在手机端改为文档流内布局（仅桌面端悬浮右上角），同屏最多 2 条
- **V1.2 一键路线规划**：一键规划到目标点的理论最短路径（可穿越普通障碍，边界墙不可穿越），地图以**闪烁虚线**展示规划路径，机器人走过的路段自动变为**稳定虚线**
- **V1.2 清障电力预算**：规划路径上的待清障目标以**红色标记**标出（电量不足未纳入的为灰色空心标记）；清障每处消耗 5% 电量，与移动耗电（0.2%/格）合并预算，自动计算电量是否足够到达并决定清障个数
- **V1.2 巡检主动发现障碍**：巡检路径被占用时优先自动绕行，绕不动则把前方障碍标记为待清障目标（地图橙色标记 + 面板一键清除），**不发告警、不中断巡检**
- **V1.2 手动清障**：地图「清障」编辑模式下点击任意障碍即可清除（每处扣 5% 电量），边界墙与非障碍格会被拒绝
- **V1.2 空电搬回**：电量耗尽弹出确认框“机器人已经没有电了，请你将机器人搬回初始点”，选择“是”后才将机器人送回起点并恢复满电
- **V1.2 标号点 / 不标号点地图**：目标点编号可一键开关，设置持久化到本地
- 深色模式、响应式布局，手机浏览器可操作
- 一键部署：Docker Compose 本地单容器（同网段手机可远程控制）/ Render 蓝图公网全栈（手机直接打开链接）

## 系统架构

```mermaid
graph TD
    Browser["浏览器 (Vue3 + Canvas)"] -->|REST + WebSocket| Backend["FastAPI 后端 :8000"]
    Backend --> Engine["仿真引擎 SimulationEngine"]
    Engine --> AStar["A* 寻路"]
    Engine --> Sensors["虚拟传感器 Sensors"]
    Engine --> Anomaly["异常检测 (规则 + IsolationForest)"]
    Engine --> Patrol["巡检调度 Patrol"]
    Backend -->|托管静态资源| Static["前端 dist"]
```

## 技术栈

- 前端：Vue 3 + Vite + Tailwind CSS + 原生 Canvas
- 后端：Python 3.11 + FastAPI + Uvicorn
- 算法 / 数据：numpy + scikit-learn（IsolationForest）
- 实时通信：WebSocket（状态帧 200ms、异常/通知事件帧）
- 部署：Docker 多阶段构建（Node 构建前端 → Python 托管）+ docker-compose + Render 蓝图（`render.yaml` 一键公网部署）

## 快速开始

### 方式一：Docker（推荐，一条命令）

```bash
docker compose -f deploy/docker-compose.yml up --build
# 浏览器打开 http://localhost:8000
```

### 方式二：本地运行（两条命令）

```bash
# 1. 后端
cd backend && pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 2. 前端（新终端）
cd frontend && npm install && npm run dev
# 浏览器打开 http://localhost:5173/?backend=http://localhost:8000
```

> 无 Docker 时也可用降级脚本：Linux/macOS 运行 `./run.sh`，Windows 运行 `run.bat`。

### 方式三：Render 一键部署（全栈公网链接，推荐演示用）

仓库根目录的 `render.yaml` 是 Render 蓝图配置，可将「前端 + 后端」作为一个 Web 服务部署到公网：

1. 登录 [render.com](https://render.com)（用 GitHub 账号登录即可，免费套餐无需信用卡）；
2. New → **Blueprint** → 选择本仓库 → Apply（Render 读取 `render.yaml` 自动创建服务）；
3. 等待构建约 3–5 分钟，得到 `https://<服务名>.onrender.com` 链接，手机与电脑均可直接打开。

说明：

- 免费套餐 15 分钟无访问会休眠，再次打开需 30–60 秒冷启动；冷启动期间前端每 5 秒自动重连，连上后恢复，无需刷新；
- 引擎为内存态，休眠重启后地图与机器人回到初始状态；
- 蓝图区域默认 `singapore`（亚洲延迟较低），若 Render 报区域相关错误，删除该行即可；
- 同源部署，无需配置 CORS（前端构建期已开启 `VITE_BACKEND_SAME_ORIGIN=true`，由后端直接托管）。

> 仅需前端公网页时，也可单独使用 GitHub Pages（仓库 `gh-pages` 分支）：Pages 为纯静态托管，跑不了后端，页面会以内置本地仿真器运行；如需接入远程后端，在链接后加 `?backend=https://后端地址` 即可（跨源需在后端环境变量 `CORS_ORIGINS` 中放行 Pages 域名）。

## API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/health` | 健康检查 |
| GET | `/api/v1/map` | 获取当前地图 |
| PUT | `/api/v1/map` | 更新地图 |
| GET | `/api/v1/path?start=x,y&goal=x,y` | A* 求路径 |
| GET | `/api/v1/sensors/latest` | 最新传感器读数 |
| GET | `/api/v1/events/anomalies` | 异常事件列表 |
| GET | `/api/v1/patrol/status` | 巡检任务状态 |
| POST | `/api/v1/plan` | 一键规划路线（穿障最短路径 + 电力预算，V1.2） |
| POST | `/api/v1/plan/execute` | 按当前规划批量清障（V1.2） |
| POST | `/api/v1/plan/cancel` | 取消当前路线规划（V1.2） |
| POST | `/api/v1/robot/clear-obstacle` | 手动清除指定障碍格（V1.2） |
| POST | `/api/v1/robot/carry-home` | 空电后将机器人搬回起点（V1.2） |
| POST | `/api/v1/map/new` | 新建空白地图（V2.0） |
| POST | `/api/v1/patrol/decision` | 巡检遇阻决策：clear / skip / stop（V2.0） |
| POST | `/api/v1/robot/clear-nearest-pending` | 清除最近的待清障障碍（V2.0） |
| GET  | `/api/v1/robot/pending` | 待清障记录列表（V2.0） |
| POST | `/api/v1/robot/reset?keep_trail=true` | 重新开始并保留尾迹（V2.0） |
| POST | `/api/v1/map/cell` | 编辑单个格子（0/1/2），不耗电（V2.1） |
| GET  | `/api/v1/maps` | 云端地图库列表（V2.1） |
| POST | `/api/v1/maps` | 保存地图到云端库（V2.1） |
| GET  | `/api/v1/maps/{id}` | 读取云端地图（V2.1） |
| POST | `/api/v1/maps/{id}/load` | 载入云端地图（V2.1） |
| DELETE | `/api/v1/maps/{id}` | 删除云端地图（V2.1） |
| WS  | `/api/v1/ws` | 状态帧（200ms）/ 异常·通知事件帧 / 指令下行 |

WebSocket 指令：`{type:"command", action:"move"|"patrol_start"|"patrol_stop"|"patrol_decision"|"reset"|"restart"|"resolve_fault"|"plan"|"clear_obstacle"|"clear_nearest_pending"|"execute_plan_clear"|"carry_home"|"cancel_plan"|"new_map", payload:{...}}`。

WebSocket 帧类型：`state`（200ms 状态帧，含 `paused` / `blocked` / `pending`）、`anomaly`、`notice`、`blocked`（巡检遇阻，前端弹窗）、`empty`（电量耗尽）。

## 目录结构

```
project-root/
├── frontend/                # Vue 前端工程
│   ├── src/services/        # 数据服务层（RobotService 接口 + Simulated/Remote 实现 + routePlanner 穿障规划）
│   └── src/components/      # 地图、控制、状态等组件
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── algorithms/      # A* 寻路
│   │   ├── services/        # 仿真引擎、传感器、异常检测、巡检调度、路线规划
│   │   ├── api/             # REST 与 WebSocket 路由
│   │   └── core/            # 配置、常量、异常
│   ├── static/dist/         # 前端构建产物（由 Docker 多阶段注入）
│   └── tests/               # pytest 单元测试
├── deploy/                  # Dockerfile 与 docker-compose.yml
├── render.yaml              # Render 一键部署蓝图（全栈公网）
├── docs/                    # 设计文档与部署指南
├── CHANGELOG.md             # 版本更新日志
├── run.sh / run.bat         # 非容器降级启动脚本
└── README.md
```

## 测试

```bash
# 后端：ruff 检查 + pytest
cd backend
pip install ruff pytest pytest-asyncio
ruff check .
pytest tests/ -v

# 前端：lint + 单元测试 + 构建
cd frontend
npm ci
npm run lint && npm test && npm run build
```

CI：仓库内置 `.github/workflows/ci.yml`（push / PR 到 main 时自动执行上述后端、前端两步，并验证 Docker 镜像可构建、可启动）；因推送令牌权限限制（细粒度令牌不支持 workflow 范围）暂未上传至 GitHub，需要时可改用带 `workflow` 权限的令牌补推启用。

## 许可证

本项目为**学习用途**的教学 / 课程作业成果。代码可自由引用与二次学习，引用时请**注明出处与作者**。未经授权不得用于商业闭源产品。
