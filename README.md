# 智能巡检机器人二维仿真系统

当前版本 V2.3.7 ｜ 源码：[chenkaixin565-coder/2d--automaticcar](https://github.com/chenkaixin565-coder/2d--automaticcar)

浏览器里开一张二维栅格地图，一台虚拟机器人在地图上走。你可以用方向键遥控它，也可以打一句话让它自己规划路线。地图就是个二维数组，用 Canvas 画出来；后端负责仿真、寻路、传感器读数和异常检测，前端只负责画和收指令。后端顺手把打包好的前端静态文件也托管了，所以整个项目一个容器就能跑完。

从最早的一版改到 V2.3.7，中间大部分时间其实花在修自己前面埋的坑上：状态帧漏字段、尾迹画成穿墙直线、清完障地图不刷新。代码算不上漂亮，但每处改动都有原因，下面尽量写清楚。

## 跑起来

有 Docker 的话最省事：

```bash
docker compose -f deploy/docker-compose.yml up --build
```

浏览器开 http://localhost:8000 就行。镜像默认不装机器学习依赖，要保持轻量；想要带上 IsolationForest，构建时加个参数：

```bash
docker build --build-arg INSTALL_ML=true -f deploy/Dockerfile .
```

没有 Docker 就开两个终端。后端：

```bash
cd backend && pip install -r requirements.txt
# 需要机器学习那套异常检测再装：pip install -r requirements-ml.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

前端：

```bash
cd frontend && npm install && npm run dev
```

打开 http://localhost:5173/?backend=http://localhost:8000 。这个 `?backend=` 参数不能省，不然前端不知道后端在哪。

两个都不想装，还有降级脚本：Linux/macOS 跑 `./run.sh`，Windows 跑 `run.bat`。

### 想让别人直接点开看

仓库根目录有 `render.yaml`，是 Render 的蓝图配置，能把前后端一起扔到公网：

1. 用 GitHub 账号登录 [render.com](https://render.com)，免费套餐不用信用卡；
2. New → Blueprint → 选这个仓库 → Apply，剩下的它自己读配置；
3. 等三五分钟，拿到 `https://<服务名>.onrender.com`，手机电脑都能开。

有几件事得提前知道。免费套餐 15 分钟没人访问就休眠，下次打开要等 30–60 秒冷启动，这期间前端每 5 秒重连一次，连上自己就恢复了，不用手动刷新。引擎是纯内存的，休眠重启之后地图和机器人回到初始状态。蓝图里区域写的 `singapore`，如果 Render 报区域相关的错，把那行删掉就好。因为是同源部署，不用配 CORS，前端构建时已经把 `VITE_BACKEND_SAME_ORIGIN=true` 打开了。

只想要一个纯前端页面，可以用仓库的 `gh-pages` 分支走 GitHub Pages。Pages 只能托管静态文件，跑不了后端，页面会自动退到内置的本地仿真器；想接远程后端就在链接后面加 `?backend=https://后端地址`，跨源的话记得把 Pages 域名放进后端的 `CORS_ORIGINS`。

## 界面上能干什么

手动遥控和自动巡检是两条基本路径。方向键或者屏幕上的摇杆都能开，巡检走的是最近邻加 A*，一路按顺序把巡检点跑完。虚拟传感器跟着仿真 tick 更新读数，三向超声波、电量、温度各一路，异常检测就看这几路的组合。没电了自己回充电点，路上撞到东西会有三下反馈：地图抖一下、弹个提示、再给一个一键排障。

地图本身可以编辑，拖出来画障碍，设起点、充电点、巡检点。最外圈是一圈固定边界墙，值 2，画不上也擦不掉，机器人也穿不过去，视觉上做成深色斜线跟普通障碍区分开，导入外部地图时会自动补齐这圈墙。

「规划」这个按钮做的是预览：先算出穿障最短路线、要清几处障、耗多少电，地图自动缩放到能看见整条路线，同时弹一个能拖动的浮层。看完再决定要不要真去，出发之后浮层自己收起。走过的路会留尾迹，细虚线，默认不显示，V2.3.7 之后每条尾迹带方向箭头，路绕回来叠在一起时也能看出往哪边走。

巡检路上被挡住会停下来问你怎么处理，三个选项：清掉继续（扣 5% 电）、跳过并记为待清障、直接停止。跳过的位置在地图上打橙色叉号，面板上有计数，也能一键清最近的那个。这里要说清楚，"清障"是两回事：编辑模式下用橡皮擦掉一格不耗电，只有巡检遇阻时选"清除并继续"才算机器人动手，扣 5%。

地图有库，本机一份（localStorage），云端一份（后端 `data/maps`），能存、能载入、能重命名、能导出成 JSON 再导回来，导入时会先校验结构。库里自带三张预设：默认厂房、仓储走廊、障碍密集区，一键切换。另外有个全屏的地图设计器，可以缩放、画普通障碍和固定屏障、改尺寸，画完存了直接载入。

其他零碎的：悬停任意格子看坐标和类型、查到这个格的理论耗电；机器人形象能上传自己的图（V2.3.1 之后存在后端，手机和电脑看到的是同一张）；深色模式；手机浏览器能用，Toast 在手机上是文档流内布局，不盖地图，同屏最多两条。

## 用了什么

前端 Vue 3 加 Vite，样式走 Tailwind，地图是原生 Canvas 一格一格画出来的，没引图形库。后端 Python 3.11 加 FastAPI 和 Uvicorn。算法都是自己写的：A*（八邻域、octile 启发、视线法平滑）、一个 BFS 对照实现、巡检用的最近邻调度。机器学习部分靠 numpy 和 scikit-learn 的 IsolationForest，自然语言解析可以选本地 Ollama。实时通信用 WebSocket，状态帧 200ms 一帧。规则和默认地图放在 `shared/` 两份 JSON 里，前后端读同一份。部署是 Docker 多阶段构建，Node 打包前端、Python 托管，配 docker-compose，公网用 Render 蓝图。

## 更新记录

按块说，因为逐条列二十多个版本号没人看得下去。

### 最近这几版基本都在修 bug（V2.3.1 到 V2.3.7）

V2.3.7 给尾迹加了方向箭头。V2.3.6 给静态资源带上了版本号 `?v=2.3.7`，入口页也禁了强缓存，之前手机上缓存着旧 JS，新旧界面来回闪，很难判断到底是不是修好了。V2.3.5 修的是后端模式下 state 帧丢了 `blocked` 和 `pending` 字段，症状很好笑：巡检遇阻的弹窗一闪就没，待清障计数永远是 0。现在整帧透传，不再挑字段。

V2.3.4 修"重新开始后尾迹多一条直线"。原因是轨迹点被连成一条线，重新开始或搬回起点这种瞬移就被画成了穿过障碍的虚线。改成按相邻格分段画，坐标不挨着就断开。V2.3.3 修清完障地图不同步：地图变更现在通过 WebSocket 推一个 `map` 帧，障碍立刻消失，不会再出现障碍还在画面上、机器人却已经穿过去了。V2.3.2 把"只去某一个巡检点"做到底，规划预览之后点「前往该点」，就真的只去那一个，结束后不会再接着跑别的。V2.3.1 是一次交互体检，把点了没反应、反应不对的那一批都过了一遍：按预览路线只去一个点、不再误报"规划已取消"、不可达时给清障建议、一键排障三种场景都生效、机器人形象多端同步。

### V2.3.0：能听懂人话，寻路也重写了

右侧面板多了个「智能指令」，输入"去 5,5 巡检"、"回充电点"、"把 3,4 的障碍清掉"这种话，系统解析成工具调用再执行，回一句人话，顺便把解析来源（规则还是模型）和耗时显示出来。

模型只能从 10 个工具里挑，坐标越界、目标格不是障碍、电量不够、超出编辑边界，都在执行前拦掉，不会出现"模型说拆哪就拆哪"。清障、改格子、复位、新建地图这类破坏性操作第一次只返回待确认，你在界面上点「确认执行」才真的动手。

模型是可选的。`AGENT_LLM_ENABLED=true` 之后接本地 Ollama，默认 `qwen2.5:7b`，6 秒超时或者返回的 JSON 不合法就自动退回规则解析。公网演示不配模型也能正常用，只是解析笨一点。

寻路从四邻域换成了八邻域：octile 启发、斜向代价 √2、不许斜着穿过墙角。200×200 的地图平均 6.3ms，路径比四邻域短 13% 左右。加了视线法平滑，用 Bresenham 做超覆盖检测看两点通不通视，把多余的拐点抽掉再逐格回填，机器人还是逐格走，电量和步数不会因为平滑而失真。四邻域没删，`GET /path?diagonal=false` 能切回去做课堂对比。另外留了个 BFS 对照实现（`bfs.py` 加 `tools/benchmark_paths.py`），一条命令就能复现"A* 只扩展了 BFS 的 15%"这个数。异常检测默认值改成了 `auto`：装了 numpy 和 scikit-learn 就用 IsolationForest，没装悄悄退回规则，`/health` 的 `anomaly_strategy` 会如实说现在跑的是哪个。

### V2.2：把工程上的窟窿补一补

之前前后端各写各的常量，改一边忘一边，对不上就出事。V2.2 把这些收进 `shared/simulation-rules.json`，电量、传感器、温度、地图尺寸全从这读，默认厂房地图放 `shared/default-map.json`，两端逐格一致。前端还加了共享规则的测试，哪一侧改了数值没跟上，测试直接红。

然后是鉴权和限流。设了 `OPERATOR_KEY`，写接口要 `X-API-Key`，WebSocket 要 `?api_key=`，前端会在你第一次点控制按钮时弹个框，密钥只存 sessionStorage。`READONLY_MODE=true` 时所有写操作返回 403，适合挂着给人看。限流是令牌桶，默认每分钟 240 次、突发 80，超了回 429 带 `Retry-After`，WebSocket 握手也算数。`/metrics` 暴露 Prometheus 格式的指标。

V2.2.1 顺手改了个体验问题：以前一进页面就要密钥，现在没密钥也能连、能看实时状态，只是不能下发指令。

### V2.1：地图库和设计器

V2.1 加了地图库、全屏地图设计器、固定屏障（值 2，机器人清不掉，只能在编辑器里手动擦，擦之前还要确认）。规划预览重做了一遍，会缩放到整条路线，浮层能拖。移动端的详情从固定抽屉改成可拖浮层，默认只占下半屏。V2.1.1 修了两个小毛病：预览时地图放大到 200% 太夸张，上限收到 90%（手机约 55%），关掉预览视角会还原；地图库入口在手机上找不到，补进底部工具条了。

### V2.0：交互整个重做

V2.0 把"规划"和"执行"拆开了，规划等于预览。巡检遇阻的三选一、待清障记录和一键清最近、新建空白图、重新开始（保留尾迹）和复位（清空尾迹）的区分，都是这一版加的。尾迹开关、随动平移、机器人形象重绘、悬停详情也在这一版。同时修了 22 项前后不一致的地方，主要是状态和显示对不上。

### V1.2：一键规划和清障

最早版本的规划可以穿普通障碍，边界墙不算，路线用闪烁虚线画，走过的段变稳定虚线。路径上的待清障目标打红标，电量不够没纳入的画灰色空心；清障一处 5%，移动 0.2% 一格，合起来算预算，自动决定能清几个。手动清障、空电搬回起点（要你确认"是"才搬）、目标点编号开关，也都是 V1.2 的东西。

## 用一句话指挥它

右侧面板点「智能指令」，直接打字：

```
现在状态怎么样
去 5,5 巡检
规划到 15,8 的路线
把 12,8 的障碍清掉     ← 这条会先要求确认
回充电点
停止巡检
```

默认走内置的中文规则解析，不装任何模型也能用。要接本地模型：

```bash
# 1. 拉模型（8GB 显存跑 7B 4bit 够用）
ollama pull qwen2.5:7b

# 2. 启动后端时打开开关
AGENT_LLM_ENABLED=true AGENT_OLLAMA_URL=http://127.0.0.1:11434 \
AGENT_OLLAMA_MODEL=qwen2.5:7b uvicorn app.main:app --port 8000
```

超时或者返回的 JSON 不合法就退回规则解析，不会把界面卡在那儿转圈。`/health` 的 `agent_mode` 会显示当前是 `rule` 还是 `ollama`。工具白名单、校验规则和一些演示脚本写在 [docs/agent.md](docs/agent.md)。

## 密钥、限流、只读

不配任何环境变量就是开放演示模式，谁进来都能操作，启动日志会打一条 WARNING 提醒你。这只是为了演示方便，别就这么扔到公网上。

| 环境变量                    | 默认      | 干什么的                                                    |
| ----------------------- | ------- | ------------------------------------------------------- |
| `OPERATOR_KEY`          | 空       | 设了之后写接口要 `X-API-Key`，WebSocket 可以只读连、下发指令要带 `?api_key=` |
| `READONLY_MODE`         | `false` | 所有写操作返回 403                                             |
| `RATE_LIMIT_PER_MINUTE` | `240`   | 每客户端每分钟请求数，`0` 关掉                                       |
| `RATE_LIMIT_BURST`      | `80`    | 允许的瞬时突发                                                 |
| `TRUST_PROXY_HEADERS`   | `true`  | 挂在反向代理后面时从 `X-Forwarded-For` 取真实 IP                     |

```bash
OPERATOR_KEY=换成你的随机长串 uvicorn app.main:app --port 8000

curl -X POST localhost:8000/api/v1/robot/move \
  -H 'Content-Type: application/json' -H 'X-API-Key: 换成你的随机长串' \
  -d '{"dx":1,"dy":0}'
```

再说一遍：密钥别写进 `VITE_*` 变量，那玩意儿会被原样打进公开的 JS 里。

限流计数和指标都在进程内存里，单实例有效。多实例部署得靠 Redis 之类的共享存储，这个项目故意没引，课程作业用不上，多一层依赖反而更容易翻车。

## 其他配置

| 环境变量                  | 默认                       | 干什么的                                                                 |
| --------------------- | ------------------------ | -------------------------------------------------------------------- |
| `ANOMALY_STRATEGY`    | `auto`                   | 有 numpy/scikit-learn 就用 IsolationForest，没有用规则；也能填 `rule` 或 `ml` 强制指定 |
| `AGENT_LLM_ENABLED`   | `false`                  | 是否用本地模型解析自然语言                                                        |
| `AGENT_OLLAMA_URL`    | `http://127.0.0.1:11434` | Ollama 地址，不往第三方转发                                                    |
| `AGENT_OLLAMA_MODEL`  | `qwen2.5:7b`             | 模型名，8GB 显存建议用 4bit 量化的 7B                                            |
| `AGENT_LLM_TIMEOUT_S` | `6`                      | 超时秒数，超了退回规则解析                                                        |
| `AGENT_MAX_GOALS`     | `12`                     | 一句话里最多能下发的巡检点数                                                       |

## 接口

除了 `/metrics`，其余都在 `/api/v1` 下面。

| 方法     | 路径                                    | 说明                                                              |
| ------ | ------------------------------------- | --------------------------------------------------------------- |
| GET    | `/api/v1/health`                      | 健康检查，带 `auth_mode`、`ws_clients`、`anomaly_strategy`、`agent_mode` |
| GET    | `/metrics`                            | Prometheus 文本指标                                                 |
| GET    | `/api/v1/map`                         | 取当前地图                                                           |
| PUT    | `/api/v1/map`                         | 换地图                                                             |
| GET    | `/api/v1/path?start=x,y&goal=x,y`     | A* 求路径，八邻域；加 `&diagonal=false` 切四邻域                             |
| POST   | `/api/v1/agent/command`               | 自然语言指令，解析、校验、执行一条龙                                              |
| GET    | `/api/v1/agent/tools`                 | Agent 的工具白名单                                                    |
| POST   | `/api/v1/robot/charge`                | 主动回充电点                                                          |
| GET    | `/api/v1/robot/avatar`                | 取自定义形象和版本号                                                      |
| PUT    | `/api/v1/robot/avatar`                | 上传形象，多端同步                                                       |
| DELETE | `/api/v1/robot/avatar`                | 恢复默认形象                                                          |
| GET    | `/api/v1/sensors/latest`              | 最新传感器读数                                                         |
| GET    | `/api/v1/events/anomalies`            | 异常事件列表                                                          |
| GET    | `/api/v1/patrol/status`               | 巡检任务状态                                                          |
| POST   | `/api/v1/plan`                        | 一键规划：穿障最短路径加电力预算                                                |
| POST   | `/api/v1/plan/execute`                | 按当前规划批量清障                                                       |
| POST   | `/api/v1/plan/cancel`                 | 取消当前规划                                                          |
| POST   | `/api/v1/robot/clear-obstacle`        | 手动清指定一格                                                         |
| POST   | `/api/v1/robot/carry-home`            | 没电了把机器人搬回起点                                                     |
| POST   | `/api/v1/map/new`                     | 新建空白图                                                           |
| POST   | `/api/v1/patrol/decision`             | 巡检遇阻决策：clear / skip / stop                                      |
| POST   | `/api/v1/robot/clear-nearest-pending` | 清掉最近的待清障                                                        |
| GET    | `/api/v1/robot/pending`               | 待清障列表                                                           |
| POST   | `/api/v1/robot/reset?keep_trail=true` | 重新开始，`keep_trail` 决定尾迹留不留                                       |
| POST   | `/api/v1/map/cell`                    | 改一格（0/1/2），不耗电                                                  |
| GET    | `/api/v1/maps`                        | 云端地图库列表                                                         |
| POST   | `/api/v1/maps`                        | 存地图到云端库                                                         |
| GET    | `/api/v1/maps/{id}`                   | 读一张云端地图                                                         |
| POST   | `/api/v1/maps/{id}/load`              | 载入云端地图                                                          |
| DELETE | `/api/v1/maps/{id}`                   | 删云端地图                                                           |
| WS     | `/api/v1/ws`                          | 状态帧 200ms，异常/通知事件帧，指令下行                                         |

WebSocket 发指令的格式：

```
{type:"command", action:"...", payload:{...}}
```

`action` 可以是 `move`、`patrol_start`、`patrol_stop`、`patrol_decision`、`reset`、`restart`、`resolve_fault`、`plan`、`clear_obstacle`、`clear_nearest_pending`、`execute_plan_clear`、`carry_home`、`go_charge`、`cancel_plan`、`new_map`。

服务端往下推的帧有 `state`（200ms 一帧，含 `paused`、`blocked`、`pending`）、`anomaly`、`notice`、`blocked`（巡检遇阻，前端弹窗用）、`empty`（电量耗尽）、`auth_state`（当前连接是只读还是能操作）、`agent`（指令执行结果）。

## 目录

```
project-root/
├── shared/                  # 前后端共用，规则和默认地图都在这
│   ├── simulation-rules.json
│   └── default-map.json
├── frontend/                # Vue 前端
│   ├── src/services/        # 数据服务层（RobotService 接口 + 本地/远程两套实现 + 路线规划 + 本地 Agent 解析）
│   └── src/components/      # 地图、控制、状态、智能指令（AgentPanel）等
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── algorithms/      # A*（八邻域和四邻域）、BFS 对照、视线法平滑
│   │   ├── services/        # 仿真引擎、传感器、异常检测、巡检调度、路线规划、Agent 指令层
│   │   ├── api/             # REST 与 WebSocket 路由
│   │   └── core/            # 配置、常量、共享规则加载、限流、指标、鉴权
│   ├── tools/               # benchmark_paths.py
│   ├── static/dist/         # 前端构建产物，Docker 多阶段构建时注入
│   └── tests/               # pytest
├── deploy/                  # Dockerfile 和 docker-compose.yml
├── .github/workflows/       # CI，后端/前端/Docker 三段
├── render.yaml              # Render 蓝图
├── docs/                    # api、algorithm、agent、ai、frontend、deploy 六份
├── CHANGELOG.md
├── run.sh / run.bat
└── README.md
```

## 测试

```bash
# 后端
cd backend
pip install -r requirements-ml.txt pytest httpx ruff
ruff check .
pytest tests/ -v          # 136 例

# 前端
cd frontend
npm ci
npm run lint && npm test && npm run build    # 96 例
```

想知道 A* 和 BFS 差多少，跑基准脚本，统计会写进 `docs/benchmark-paths.json`：

```bash
cd backend
python tools/benchmark_paths.py --size 50 --density 0.2 --samples 100 --perf \
    --json ../docs/benchmark-paths.json
```

CI 在 `.github/workflows/ci.yml`，push 或 PR 到 `main` 时跑：后端 ruff 加 pytest、前端 eslint 加 vitest 加 build、Docker 构建完探活 `/api/v1/health`。顺带说一句，这个文件之前一直推不上去，因为令牌是细粒度的、不含 `workflow` 范围，换成有权限的令牌推一次就自动生效了。

## 还没做好的地方

留着给自己记的，也省得别人踩同样的坑。

异常检测在样本很少的时候基本靠猜。IsolationForest 要足够的点才有意义，机器人刚起步那几十帧里，规则基线反而更准，这个阈值我一直没调明白。Agent 的规则解析只认中文，英文输入会走到兜底话术上。地图设计器在手机上能用，但用手指画格子精度很差，勉强能改一两格，正经画图还是得用电脑。限流和指标是进程内存的，前面说了，多实例就废了。还有一点：引擎状态全在内存里，刷新浏览器不会丢，重启后端就全回初始状态，没有做存档。

## 关于这份代码

教学和课程作业的成果，随便看随便抄着学，引用的时候注明出处和作者就行。别拿去包一层做商业闭源产品，这个没得商量。
