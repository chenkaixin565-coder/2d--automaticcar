# 接口文档（REST + WebSocket）

> 适用版本：**V2.3.3**
> 整理依据：`backend/app/api/rest.py` 与 `websocket.py` 的实际实现；接口有变动时以代码为准。
> 在线可交互版：`https://irm-sim-2d.onrender.com/docs`

---

## 1. 通用约定

| 项 | 约定 |
|---|---|
| 基地址 | 同源部署为 `https://<域名>`；本地为 `http://127.0.0.1:8000` |
| 数据格式 | JSON（UTF-8），请求头 `Content-Type: application/json` |
| 坐标 | `[x, y]`，x 为列、y 为行，左上角为 `(0, 0)`，与前端 Canvas 一致 |
| 栅格取值 | `0` 可通行、`1` 普通障碍（机器人可清除）、`2` 固定屏障（不可穿越、不可清除） |
| 时间 | 异常事件的 `time` 为 ISO 8601 UTC 字符串 |
| 版本 | `GET /api/v1/health` 的 `version` 字段 |

### 1.1 鉴权（V2.2）

服务端可通过环境变量 `OPERATOR_KEY` 开启写操作鉴权：

| 场景 | 行为 |
|---|---|
| 未配置 `OPERATOR_KEY` | 开放演示模式，读写都放行 |
| 配置了 `OPERATOR_KEY` | **读接口公开**；`POST/PUT/PATCH/DELETE` 需要 `X-API-Key: <密钥>` |
| `READONLY_MODE=true` | 所有写操作返回 **403**，读正常 |

WebSocket 的连接本身允许只读接入（会收到 `state` 帧）；下发控制指令时才校验密钥，
密钥通过 `?api_key=<密钥>` 传入（浏览器无法自定义握手头）。

### 1.2 错误约定

| 状态码 | 含义 | 响应体 |
|---|---|---|
| 401 | 缺少或错误的操作密钥 | `{"detail": "需要操作密钥"}` |
| 403 | 只读模式 | `{"detail": "只读模式：当前部署不允许修改状态"}` |
| 404 | 地图 / 资源不存在 | `{"detail": "地图不存在"}` |
| 422 | 参数校验失败（尺寸、坐标、取值越界） | `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` |
| 429 | 触发限流（默认 240 次/分钟、突发 80） | `{"detail": "请求过于频繁，请稍后再试"}`，带 `Retry-After` |

---

## 2. 地图与编辑

| 方法 | 路径 | 说明 | 写权限 |
|---|---|---|---|
| GET | `/api/v1/map` | 获取当前地图 | 否 |
| PUT | `/api/v1/map` | 整图替换（校验尺寸、边界、关键点） | 是 |
| POST | `/api/v1/map/new` | 新建空白地图（仅保留四周墙） | 是 |
| POST | `/api/v1/map/cell` | 编辑单个格子（**不耗电**） | 是 |
| POST | `/api/v1/map/suggest-removal` | 建议拆除的最小障碍（只建议，不执行） | 是 |
| POST | `/api/v1/map/remove-obstacle` | 旧版兼容，等价于上一条 | 是 |

### GET /api/v1/map

```json
{
  "width": 30,
  "height": 20,
  "grid": [[1, 1, 1], [1, 0, 0]],
  "start": [1, 1],
  "goals": [[5, 5], [15, 8]],
  "charge_point": [28, 18]
}
```

### PUT /api/v1/map

请求体为完整 `GridMap`。约束：

- `width` / `height` ≥ 3，`grid` 行数必须等于 `height`、每行长度等于 `width`
- 最外环必须是墙（服务端会强制补齐）
- `start` / `goals` / `charge_point` 必须落在可通行格，否则 **422**

### POST /api/v1/map/cell

```json
{ "x": 5, "y": 6, "value": 2 }
```

| 字段 | 约束 |
|---|---|
| `x` / `y` | 整数，需在地图内且不是最外环 |
| `value` | `0` 通行 / `1` 石头 / `2` 固定屏障 / `3` 沙子 / `4` 金刚石 |

V2.4.0 起支持三种可清障材质：石头（5%）、沙子（2%）、金刚石（20%）；`2` 仍是不可清除的固定屏障。

编辑不扣电量；若该格是起点、充电点、巡检点或机器人当前所在格，拒绝修改（返回 notice）。

### POST /api/v1/map/new

```json
{ "width": 20, "height": 12 }
```

`width` / `height` 范围 **10–60**，缺省 30×20。返回新地图，机器人复位。

---

## 3. 地图库

| 方法 | 路径 | 说明 | 写权限 |
|---|---|---|---|
| GET | `/api/v1/maps` | 列表（仅元信息） | 否 |
| POST | `/api/v1/maps` | 保存地图 | 是 |
| GET | `/api/v1/maps/{map_id}` | 读取完整地图 | 否 |
| DELETE | `/api/v1/maps/{map_id}` | 删除 | 是 |
| POST | `/api/v1/maps/{map_id}/load` | 载入并切换为当前地图 | 是 |

保存请求：

```json
{ "name": "厂房 A 区", "map": { "width": 30, "height": 20, "grid": [], "start": [1,1], "goals": [], "charge_point": [28,18] }, "id": null }
```

`name` 长度 1–40；`id` 传入表示覆盖保存。列表项包含 `id / name / width / height / goals / updated_at`。
载入成功后机器人复位，返回 `{"map": {...}, "id": "..."}`。

---

## 4. 机器人控制

| 方法 | 路径 | 说明 | 写权限 |
|---|---|---|---|
| POST | `/api/v1/robot/move` | 单步移动（会中断巡检） | 是 |
| POST | `/api/v1/robot/reset?keep_trail=false` | 复位；`true` 保留尾迹 | 是 |
| POST | `/api/v1/robot/resolve` | 一键排障（清除正前方障碍） | 是 |
| POST | `/api/v1/robot/clear-obstacle` | 手动清障（按处扣电） | 是 |
| POST | `/api/v1/robot/clear-nearest-pending` | 清除最近的待清障障碍 | 是 |
| GET | `/api/v1/robot/pending` | 待清障记录 | 否 |
| POST | `/api/v1/robot/carry-home` | 空电后搬回起点 | 是 |
| POST | `/api/v1/robot/charge` | 主动返回充电点（V2.3.0） | 是 |
| GET | `/api/v1/robot/avatar` | 获取自定义形象与版本号（V2.3.1） | 否 |
| PUT | `/api/v1/robot/avatar` | 上传自定义形象（data URL），广播 `avatar` 帧（V2.3.1） | 是 |
| DELETE | `/api/v1/robot/avatar` | 恢复默认形象（V2.3.1） | 是 |
| GET | `/api/v1/robot/trail` | 已走过的轨迹，返回 `{"trail": [[x,y], ...]}` | 否 |

移动请求 `dx/dy` 取值 **-1 / 0 / 1**。响应为机器人状态：

```json
{
  "x": 2, "y": 1, "theta": 0.0, "battery": 99.8, "speed": 1.0, "mode": "manual",
  "path": [],
  "sensors": { "front": null, "left": 0.5, "right": null, "temperature": 35.1 },
  "patrol": { "running": false, "paused": false, "current_goal": null, "progress": 0.0,
              "completed": 0, "total": 0, "path_remain": 0, "blocked_by": null },
  "plan": null, "paused": false, "blocked": null, "pending": [], "trail_len": 2
}
```

`mode` 取值：`manual` / `patrol` / `charging` / `blocked` / `empty`。

---

## 5. 路径与规划

| 方法 | 路径 | 说明 | 写权限 |
|---|---|---|---|
| GET | `/api/v1/path?start=1,1&goal=5,5` | A* 调试接口 | 否 |
| POST | `/api/v1/plan` | 预览路线（穿障最短路径 + 电力预算） | 是 |
| POST | `/api/v1/plan/cancel` | 取消预览 | 是 |
| POST | `/api/v1/plan/execute` | 按当前规划批量清障 | 是 |

`/path` 返回（V2.3.0 起为八邻域，斜向一步代价 √2）：

```json
{
  "path": [[1,1],[2,2],[3,3],[4,4],[5,5]],
  "visited_count": 5,
  "cost": 5.656854249492381,
  "reachable": true,
  "error": null
}
```

`start` / `goal` 必须是 `x,y` 格式，否则 **422**；越界或障碍起终点返回空路径，
并用 `error` 给出原因：`out_of_bounds` / `start_blocked` / `goal_blocked` / `unreachable` / `empty_map`。

`/plan` 请求 `{"goal": [5, 5]}`，返回：

```json
{
  "goal": [5, 5],
  "path": [[1,1],[1,2],[1,3],[1,4],[1,5],[2,5],[3,5],[4,5],[5,5]],
  "obstacles": [], "clearable": [],
  "move_cost": 1.6, "clear_cost": 0.0, "total_cost": 1.6,
  "battery": 100.0, "clear_unit_cost": 5.0,
  "reachable": true, "enough": true, "message": ""
}
```

- `obstacles`：路径上需要清除的格子
- `clearable`：电力预算内实际能清的格子
- `enough=false` 表示电量只够清一部分
- **预览不移动机器人**；`/plan/execute` 才批量清障

---

## 6. 巡检

| 方法 | 路径 | 说明 | 写权限 |
|---|---|---|---|
| POST | `/api/v1/patrol/start` | 开始巡检（缺省用地图巡检点） | 是 |
| POST | `/api/v1/patrol/stop` | 停止 | 是 |
| POST | `/api/v1/patrol/decision` | 遇阻决策 `clear` / `skip` / `stop` | 是 |
| GET | `/api/v1/patrol/status` | 巡检状态 | 否 |

`/patrol/status` 返回：

```json
{ "running": true, "paused": false, "current_goal": [5, 5], "progress": 0.2,
  "completed": 1, "total": 5, "path_remain": 3, "blocked_by": null }
```

`progress` 为 **0–1**；遇阻时 `blocked_by` 为障碍坐标，前端据此弹窗。
`clear` 扣 5% 电量并续跑；`skip` 记入待清障并跳到下一个点；`stop` 结束任务。

---

## 7. 感知与异常

| 方法 | 路径 | 说明 | 写权限 |
|---|---|---|---|
| GET | `/api/v1/sensors/latest` | 三向测距 + 温度 | 否 |
| GET | `/api/v1/events/anomalies` | 历史异常事件 | 否 |
| DELETE | `/api/v1/events/anomalies` | 清空历史 | 是 |

传感器示例：

```json
{ "front": 2.5, "left": null, "right": 4.0, "temperature": 35.4 }
```

`null` 表示超出 5m 量程。异常事件结构：

```json
{ "time": "2026-10-27T00:00:00+00:00", "type": "low_battery",
  "message": "电量不足 18%，即将自动返航充电", "position": [12, 7] }
```

`type` 取值：`low_battery` / `obstacle` / `sensor_fault` / `overheat` / `ml_anomaly`。

---

## 8. 系统

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/health` | 健康检查（含 `auth_mode` / `ws_clients` / `tick_alive`） |
| GET | `/metrics` | Prometheus 文本指标（不在 OpenAPI schema 中） |

健康检查示例：

```json
{ "status": "ok", "version": "V2.3.0", "tick_errors": 0, "last_tick_age_s": 0.1,
  "tick_alive": true, "auth_mode": "operator-key", "rate_limit_per_minute": 240,
  "ws_clients": 1, "anomaly_strategy": "MLAnomalyDetector", "agent_mode": "rule" }
```

`anomaly_strategy` 为实际生效的检测器类名（`RuleAnomalyDetector` / `MLAnomalyDetector`），
`agent_mode` 为 `rule`（内置规则解析）或 `ollama`（接本地大模型）。

`/metrics` 关键指标：`irm_uptime_seconds`、`http_requests_total{method,status}`、
`rate_limited_total`、`auth_rejected_total`、`irm_ws_clients`、`irm_engine_battery_percent`、
`irm_engine_position{axis}`、`irm_patrol_running`、`irm_tick_errors_total`。

---

## 9. WebSocket

连接：`ws(s)://<host>/api/v1/ws`（需要操作时追加 `?api_key=<密钥>`）。

### 9.1 服务端 → 客户端

| 帧类型 | 频率 | 说明 |
|---|---|---|
| `state` | 200ms | 机器人状态（字段同第 4 节响应） |
| `auth_state` | 连接时一次 | `{can_control, readonly, auth_mode}` |
| `anomaly` | 事件触发 | 异常事件 |
| `notice` | 事件触发 | 操作提示（规划完成、清障成功等） |
| `blocked` | 事件触发 | 巡检遇阻（V2.3.1 增加 `reason`：`obstacle` / `barrier` / `unreachable`，不可达时带 `goal`），含 `cell / message / battery / clear_cost` |
| `avatar` | 形象变更 | 只带 `version`，客户端据此去 `GET /robot/avatar` 拉图（V2.3.1） |
| `map` | 地图变更 | 清障 / 编辑 / 新建地图后推送权威地图，前端直接覆盖（V2.3.3） |
| `empty` | 事件触发 | 电量耗尽 |
| `agent` | 指令执行后 | Agent 执行结果（字段同第 10 节返回体） |
| `auth_required` | 指令被拒时 | `{code, readonly, message}`，前端据此弹密钥框 |

### 9.2 客户端 → 服务端

```json
{ "type": "command", "action": "move", "payload": { "dx": 1, "dy": 0 } }
```

可用 `action`：`move`、`patrol_start`、`patrol_stop`、`patrol_decision`、`reset`、`restart`、
`resolve_fault`、`plan`、`cancel_plan`、`clear_obstacle`、`clear_nearest_pending`、
`execute_plan_clear`、`carry_home`、`go_charge`、`set_cell`、`new_map`。

自然语言指令不走 WebSocket：用 `POST /api/v1/agent/command`（需要写权限），
执行完成后服务端会把 `agent` 帧广播给所有在线客户端。

### 9.3 关闭码

| 码 | 含义 |
|---|---|
| 4429 | 触发限流，连接被关闭 |

> `4401` / `4403` 不是关闭码，而是 `auth_required` 帧里的 `code` 字段：
> 连接保持打开，只是控制指令被拒绝。这样只读访问者仍能继续看实时状态。

---

## 10. Agent 指令层（V2.3.0）

把一句中文翻成一次受控的工具调用。解析器默认是内置规则（离线可用），设置
`AGENT_LLM_ENABLED=true` 后改为本地 Ollama（失败自动回退规则）。

| 方法 | 路径 | 说明 | 写权限 |
|---|---|---|---|
| POST | `/api/v1/agent/command` | 执行一条自然语言指令 | 是 |
| GET | `/api/v1/agent/tools` | 工具白名单（名称、说明、参数、示例） | 否 |

请求：

```json
{ "text": "把 3,4 的障碍清掉", "confirm": false }
```

返回：

```json
{
  "text": "把 3,4 的障碍清掉",
  "understood": true,
  "tool": "clear_obstacle",
  "args": { "cell": [3, 4] },
  "source": "rule",
  "executed": false,
  "need_confirm": true,
  "ok": false,
  "message": "这条指令会修改现场状态：清除指定格子的障碍（清除 [3, 4] 的障碍，扣 5% 电量）。确认执行吗？",
  "result": null,
  "latency_ms": 0.3
}
```

- `source`：`rule`（规则解析）/ `llm`（本地大模型）/ `rule-fallback`（大模型失败回退）；
- `need_confirm=true` 时**尚未执行**，前端确认后带 `"confirm": true` 再发一次；
  清障、改格子、复位、新建地图四类破坏性操作都必须确认；
- `executed` 表示是否真的执行；`ok` 表示执行是否成功；
- 越界坐标、非障碍格、电量不足、边界编辑等校验失败时 `understood=true` 但
  `executed=false`，`message` 是给人看的原因，HTTP 状态码仍是 200。

可用工具：

| 工具 | 参数 | 破坏性 | 说明 |
|---|---|---|---|
| `status` | — | 否 | 位置、电量、模式、巡检进度 |
| `plan_route` | `goal:[x,y]` | 否 | 只生成路线预览，不移动 |
| `start_patrol` | `goals?:[[x,y]]` | 否 | 开始巡检，缺省用地图巡检点 |
| `stop_patrol` | — | 否 | 停止巡检 |
| `go_charge` | — | 否 | 返回充电点 |
| `move` | `dx,dy` | 否 | 手动移动一格 |
| `clear_obstacle` | `cell:[x,y]` | 是 | 清障，扣 5% 电量 |
| `set_cell` | `x,y,value` | 是 | 编辑地图格子（0/1/2） |
| `reset` | — | 是 | 复位并恢复满电 |
| `new_map` | `width,height` | 是 | 新建空白地图 |

---

## 11. 版本差异

| 版本 | 变更 |
|---|---|
| V2.4.0 | 地图格子新增 `3=沙子`、`4=金刚石`；`build_plan` 的 `clear_cost` 改为按材质累加；`set_cell` 接受 0~4 |
| V2.3.3 | 新增 `map` 帧：地图变更后广播权威地图；前端按帧覆盖，修复"清障后地图不同步" |
| V2.3.1 | 新增 `/robot/avatar` 三件套与 `avatar` 帧；`blocked` 帧增加 `reason`/`goal`；Agent 支持「第 N 号巡检点」；开始巡检会静默作废预览 |
| V2.3.0 | 新增 `/agent/command`、`/agent/tools`、`/robot/charge`；`/path` 改八邻域并返回 `reachable` / `error`；新增 `agent` 帧与 `go_charge` 指令 |
| V2.2.1 | WS 支持只读接入；新增 `auth_state` 帧；指令级鉴权 |
| V2.2.0 | 新增操作密钥、限流、`/metrics`、共享规则 |
| V2.1 | 地图库、单格编辑、固定屏障 |
| V2.0 | 巡检遇阻决策、待清障、规划预览、新建地图 |
