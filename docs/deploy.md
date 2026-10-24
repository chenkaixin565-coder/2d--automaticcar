# 部署与多端访问指南

本文档覆盖四种使用场景与常见问题排查。系统为**前后端一体单容器**：FastAPI 后端在 `:8000` 同时托管前端静态页，浏览器打开即是用后端仿真的完整版本。

---

## 场景一：本机开发（前后端分离热更新）

适合边改代码边看效果，前端走 Vite 热更新，后端走 uvicorn。

```bash
# 终端 1：启动后端（默认 8000 端口，200ms tick）
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 终端 2：启动前端开发服务器（5173 端口）
cd frontend
npm install
npm run dev
```

前端开发服务器默认是**离线仿真版**（不连后端）。要联调后端，在浏览器地址栏加参数：

```
http://localhost:5173/?backend=http://localhost:8000
```

> ![开发模式首页](docs/screenshots/desktop-home.png)
>
> 上图为后端模式首页：右上角显示"后端服务"徽章，后端日志显示 WebSocket 连接。

---

## 场景二：本机 / 服务器 Docker 部署（推荐上线方式）

无需安装 Node/Python 环境，一条命令拉起整套系统。

```bash
# 构建并启动（首次会构建镜像，耐心等待依赖安装）
docker compose -f deploy/docker-compose.yml up --build

# 后台运行
docker compose -f deploy/docker-compose.yml up -d --build
```

启动后浏览器访问 `http://localhost:8000`。

自定义端口与仿真速率：

```bash
PORT=9000 TICK_INTERVAL_MS=100 docker compose -f deploy/docker-compose.yml up -d --build
```

无 Docker 的降级方案（Linux/Mac 与 Windows 各一份）：

```bash
# Linux / macOS
./run.sh

# Windows（CMD，需先装 Python 与 Node）
run.bat
```

> ![Docker 部署首页](docs/screenshots/docker-home.png)
>
> 浏览器打开 http://localhost:8000 即看到系统首页（同源托管前端 + 后端）。

---

## 场景三：手机访问（同 Wi-Fi 控制机器人）

这是展示与答辩最直观的方式：电脑跑服务，手机当遥控器。

1. 电脑与手机连到**同一个 Wi-Fi**（同一局域网）。
2. 电脑上确认服务已启动并绑定 `0.0.0.0`（Docker 默认如此；本机 `uvicorn` 也用了 `--host 0.0.0.0`）。
3. 查电脑局域网 IP：
   - Windows：`ipconfig` → 看"无线局域网适配器 WLAN"的 IPv4 地址，如 `192.168.1.23`
   - macOS / Linux：`ifconfig` 或 `ip a` → 看 `wlan0` / `en0` 的 `inet` 地址
4. 手机浏览器打开：

   ```
   http://<电脑局域网IP>:8000
   ```

   例：`http://192.168.1.23:8000`

5. 手机端用屏幕摇杆或方向键即可控制机器人移动、下发巡检任务。

> ![手机端控制](docs/screenshots/mobile-home.png)
>
> 手机竖屏显示虚拟摇杆与地图，右上角徽章标明当前为"后端服务"模式。

---

## 场景四：常见问题排查

**1) 端口被占用（地址已在使用）**

- 换端口：`PORT=9000 docker compose -f deploy/docker-compose.yml up -d --build`
- 或释放占用：`lsof -i :8000`（macOS/Linux）后结束对应进程；Windows 用 `netstat -ano | findstr 8000`。

**2) Windows 防火墙拦截**

- 首次运行 Docker / uvicorn 时，系统可能弹窗询问"是否允许访问网络"，需选**专用网络**允许。
- 手动放行入站规则：Windows Defender 防火墙 → 高级设置 → 入站规则 → 新建规则 → 端口 → TCP → 特定本地端口 `8000` → 允许连接。

**3) 手机无法访问的排查清单**

| 步骤 | 操作 | 正常表现 |
|---|---|---|
| ① | 电脑 `ping <手机IP>` / 手机 `ping <电脑IP>` | 双方能互通 |
| ② | 电脑本机 `curl http://localhost:8000/api/v1/health` | 返回 `{"status":"ok",...}` |
| ③ | 手机浏览器访问 `http://<电脑IP>:8000` | 能打开首页 |
| ④ | 若③失败，检查电脑防火墙入站规则是否放行 8000 | 放行后恢复 |
| ⑤ | 确认手机与电脑在同一 Wi-Fi（不是访客网络/隔离 AP） | 同一网段 |

**4) 镜像构建慢 / 失败**

- `scikit-learn` + `numpy` 体积较大，首次构建需 2~5 分钟，属正常。
- 若 `npm ci` 失败，确认 `frontend/package-lock.json` 已提交；若 `pip install` 失败，确认 `backend/requirements.txt` 版本存在。
