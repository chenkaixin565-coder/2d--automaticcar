"""
Agent 指令层（自然语言 → 白名单工具调用）。

模块功能：把用户的一句话（"去 5,5 巡检"、"把 3,4 的墙拆了"、"回充电点"）
翻译成一次受控的工具调用，交给仿真引擎执行，并把执行结果转成一句人话返回。

设计要点（答辩时可直接讲）：

1. **工具白名单**：模型只能从 TOOL_SPECS 里选动作，不能生成代码、URL 或新的
   接口调用；未知工具一律拒绝。
2. **参数 schema 校验**：坐标越界、目标格是障碍、电量不足、地图尺寸非法等情况
   在执行前就被拦下，模型"说了算"的只有自然语言，不包含权限。
3. **破坏性操作二次确认**：清障、改格子、新建地图、复位这类不可逆动作，第一次
   调用只返回"待确认"，必须带 confirm=True 再发一次才真正执行。
4. **离线兜底**：默认不接大模型，用内置中文规则解析；配置 AGENT_LLM_ENABLED=true
   后才会尝试本地 Ollama，任何超时/报错/JSON 不合法都会静默回退到规则解析。
5. **可解释**：返回体里带 source（rule / llm / rule-fallback）、tool、args 与
   latency_ms，前端把"它听成了什么、执行了没有"原样展示给用户。

作者：智能巡检机器人二维仿真系统 V2.3.0 开发组
日期：2026-10-30
版本：V2.3.0
"""

import asyncio
import json
import logging
import re
import time
import urllib.error
import urllib.request

from app.core import config
from app.core.constants import CELL_BARRIER, CLEARABLE_CELLS, MATERIAL_LABELS, MODE_EMPTY

logger = logging.getLogger("simulation.agent")

# ---------------------------------------------------------------------------
# 工具白名单
# ---------------------------------------------------------------------------

TOOL_SPECS: dict[str, dict] = {
    "status": {
        "description": "查询机器人当前位置、电量、模式与巡检进度",
        "args": {},
        "destructive": False,
        "examples": ["现在状态怎么样", "电量还有多少", "机器人在哪"],
    },
    "plan_route": {
        "description": "规划到目标点的路线（只预览，不移动机器人）",
        "args": {"goal": "[x, y] 目标坐标"},
        "destructive": False,
        "examples": ["规划到 5,5 的路线", "去 12,8 怎么走"],
    },
    "start_patrol": {
        "description": "开始自动巡检；给出巡检点则只巡这些点，否则用地图上的巡检点",
        "args": {"goals": "[[x, y], ...]，可省略"},
        "destructive": False,
        "examples": ["开始巡检", "去 5,5 和 8,3 巡检"],
    },
    "stop_patrol": {
        "description": "停止当前自动巡检任务",
        "args": {},
        "destructive": False,
        "examples": ["停止巡检", "别走了"],
    },
    "go_charge": {
        "description": "让机器人返回充电点",
        "args": {},
        "destructive": False,
        "examples": ["回充电点", "去充电", "返航"],
    },
    "move": {
        "description": "手动移动一格（上下左右或沿当前朝向前后）",
        "args": {"dx": "-1 / 0 / 1", "dy": "-1 / 0 / 1"},
        "destructive": False,
        "examples": ["向右移动一格", "前进两步"],
    },
    "clear_obstacle": {
        "description": "清除指定格子上的障碍物（扣除 5% 电量）",
        "args": {"cell": "[x, y] 障碍坐标"},
        "destructive": True,
        "examples": ["把 3,4 的障碍清掉", "清除 6,2 的墙"],
    },
    "set_cell": {
        "description": "编辑地图：把某格设为空闲 / 石头 / 固定屏障 / 沙子 / 金刚石（不耗电）",
        "args": {"x": "列坐标", "y": "行坐标", "value": "0=空闲 1=石头 2=屏障 3=沙子 4=金刚石"},
        "destructive": True,
        "examples": ["把 7,7 设成障碍", "清除 4,4 这个格子"],
    },
    "reset": {
        "description": "复位机器人到起点并恢复满电",
        "args": {},
        "destructive": True,
        "examples": ["复位", "回到起点"],
    },
    "new_map": {
        "description": "新建一张只有边界墙的空白地图",
        "args": {"width": "10~60", "height": "10~60"},
        "destructive": True,
        "examples": ["新建一张 30x20 的地图"],
    },
}

DESTRUCTIVE_TOOLS = {name for name, spec in TOOL_SPECS.items() if spec["destructive"]}

MODE_LABELS = {
    "manual": "手动",
    "patrol": "自动巡检",
    "charging": "返航充电",
    "blocked": "受阻",
    "empty": "电量耗尽",
}

# 文本归一化后用于匹配的坐标：支持 "5,5" / "5，5" / "5、5" / "5x5" / "(5,5)"。
_COORD_RE = re.compile(r"(\d{1,3})\s*[,，、xX×]\s*(\d{1,3})")
_GRID_RE = re.compile(r"(\d{1,2})\s*[xX×*]\s*(\d{1,2})")
# 巡检点序号："3 号巡检点" / "第 3 个巡检点" / "2#点"（V2.3.1）。
_GOAL_INDEX_RE = re.compile(r"(?:第\s*)?(\d{1,2})\s*(?:号|个|#)\s*(?:巡检点|点|目标)")

# 常见口语 → 意图关键词。顺序即优先级，先匹配到的先赢。
_STOP_WORDS = ("停止", "停下", "停住", "别走", "别动", "取消巡检", "停止巡检", "stop")
_STATUS_WORDS = ("状态", "电量", "多少电", "在哪", "位置", "报告", "情况", "怎么样")
_CHARGE_WORDS = ("充电", "回充", "返航", "回血", "补电")
_CLEAR_WORDS = ("清除", "清掉", "清障", "拆掉", "拆了", "铲掉", "移走", "去掉", "删掉")
_PATROL_WORDS = ("巡检", "巡逻", "巡查", "patrol")
_PLAN_WORDS = ("规划", "路线", "预览", "怎么走", "路径", "导航")
_RESET_WORDS = ("复位", "重置", "回起点", "回到起点", "重置位置")
_NEW_MAP_WORDS = ("新建地图", "新建一张", "新地图", "重新开始画")
_FORWARD_WORDS = ("前进", "往前", "向前走", "前进一格")
_BACKWARD_WORDS = ("后退", "往后", "向后走")
_UP_WORDS = ("向上", "往上", "上移", "上面")
_DOWN_WORDS = ("向下", "往下", "下移", "下面")
_LEFT_WORDS = ("向左", "往左", "左移", "左边")
_RIGHT_WORDS = ("向右", "往右", "右移", "右边")
_SET_WORDS = ("设成", "设为", "设置为", "改成", "标记为")
_BARRIER_WORDS = ("屏障", "固定墙", "永久墙")
_OBSTACLE_WORDS = ("障碍", "墙", "阻挡")
_EMPTY_WORDS = ("空闲", "空地", "通行", "清空")


class AgentError(ValueError):
    """Agent 参数校验失败，message 直接面向用户展示。"""


def _normalize(text: str) -> str:
    """
    归一化用户输入：全角数字/标点转半角、压缩空白。

    :param text: 原始输入。
    :return: 归一化后的文本。
    """
    table = str.maketrans(
        "０１２３４５６７８９，。；：！？（）：", "0123456789,.;:!?():"
    )
    return re.sub(r"\s+", " ", (text or "").translate(table)).strip()


def _has(text: str, words: tuple[str, ...]) -> bool:
    """判断文本是否包含任一关键词。"""
    return any(word in text for word in words)


def _extract_coords(text: str) -> list[list[int]]:
    """提取文本里的全部坐标对，返回 [[x, y], ...]。"""
    return [[int(x), int(y)] for x, y in _COORD_RE.findall(text)]


def _extract_goal_index(text: str) -> int | None:
    """
    提取"第几个巡检点"的序号（从 1 开始）。

    :param text: 归一化后的文本。
    :return: 序号；没有则返回 None。
    """
    match = _GOAL_INDEX_RE.search(text)
    return int(match.group(1)) if match else None


def parse_rules(text: str, heading: tuple[int, int] = (1, 0)) -> dict:
    """
    用内置中文规则把一句话解析成工具调用。

    这是"离线兜底"解析器：不联网、不确定、可预测。规则覆盖演示脚本里会用到的
    说法，识别不了就返回 understood=False，而不是猜一个动作去执行。

    V2.3.1 新增"第 N 号巡检点"：把序号交给校验层换算成坐标，支持
    "去 3 号巡检点""规划到第 2 个巡检点"。

    :param text: 归一化前的原始输入。
    :param heading: 机器人当前朝向对应的单位步长，用于解释"前进/后退"。
    :return: {'tool': str|None, 'args': dict, 'reason': str}。
    """
    normalized = _normalize(text)
    coords = _extract_coords(normalized)
    goal_index = _extract_goal_index(normalized)

    if _has(normalized, _STOP_WORDS):
        return {"tool": "stop_patrol", "args": {}, "reason": "停止巡检"}
    if _has(normalized, _STATUS_WORDS):
        return {"tool": "status", "args": {}, "reason": "查询状态"}
    if _has(normalized, _CHARGE_WORDS):
        return {"tool": "go_charge", "args": {}, "reason": "返回充电点"}

    if _has(normalized, _CLEAR_WORDS) and coords:
        return {"tool": "clear_obstacle", "args": {"cell": coords[0]}, "reason": "清除障碍"}

    # 规划意图要先于巡检判断：\"规划到 3 号巡检点\"里也含"巡检"二字。
    if _has(normalized, _PLAN_WORDS):
        if coords:
            return {"tool": "plan_route", "args": {"goal": coords[0]}, "reason": "规划路线"}
        if goal_index is not None:
            return {"tool": "plan_route", "args": {"goal_index": goal_index}, "reason": "规划到指定巡检点"}

    if _has(normalized, _PATROL_WORDS):
        if coords:
            return {"tool": "start_patrol", "args": {"goals": coords}, "reason": "开始巡检"}
        if goal_index is not None:
            return {
                "tool": "start_patrol",
                "args": {"goal_index": goal_index},
                "reason": "前往指定巡检点",
            }
        return {"tool": "start_patrol", "args": {}, "reason": "开始巡检"}

    if _has(normalized, _RESET_WORDS):
        return {"tool": "reset", "args": {}, "reason": "复位"}

    grid_match = _GRID_RE.search(normalized)
    if _has(normalized, _NEW_MAP_WORDS) and grid_match:
        return {
            "tool": "new_map",
            "args": {"width": int(grid_match.group(1)), "height": int(grid_match.group(2))},
            "reason": "新建地图",
        }

    if _has(normalized, _SET_WORDS) and coords:
        value = 0
        if _has(normalized, _BARRIER_WORDS):
            value = 2
        elif _has(normalized, ("金刚石", "钻石", "diamond")):
            value = 4
        elif _has(normalized, ("沙子", "沙地", "sand")):
            value = 3
        elif _has(normalized, _OBSTACLE_WORDS):
            value = 1
        elif _has(normalized, _EMPTY_WORDS):
            value = 0
        return {
            "tool": "set_cell",
            "args": {"x": coords[0][0], "y": coords[0][1], "value": value},
            "reason": "编辑地图格子",
        }

    if _has(normalized, _FORWARD_WORDS):
        return {"tool": "move", "args": {"dx": int(heading[0]), "dy": int(heading[1])}, "reason": "前进"}
    if _has(normalized, _BACKWARD_WORDS):
        return {"tool": "move", "args": {"dx": -int(heading[0]), "dy": -int(heading[1])}, "reason": "后退"}
    if _has(normalized, _UP_WORDS):
        return {"tool": "move", "args": {"dx": 0, "dy": -1}, "reason": "向上"}
    if _has(normalized, _DOWN_WORDS):
        return {"tool": "move", "args": {"dx": 0, "dy": 1}, "reason": "向下"}
    if _has(normalized, _LEFT_WORDS):
        return {"tool": "move", "args": {"dx": -1, "dy": 0}, "reason": "向左"}
    if _has(normalized, _RIGHT_WORDS):
        return {"tool": "move", "args": {"dx": 1, "dy": 0}, "reason": "向右"}

    # 只给了坐标、没给动作：默认理解为"规划一条过去的路线"，只预览不执行。
    if coords and _has(normalized, ("去", "到", "前往", "走")):
        return {"tool": "plan_route", "args": {"goal": coords[0]}, "reason": "规划路线"}

    return {"tool": None, "args": {}, "reason": "没有识别出可执行的指令"}


# ---------------------------------------------------------------------------
# 参数校验
# ---------------------------------------------------------------------------


def _as_int(value, field: str) -> int:
    """把参数强制转成整数，失败时抛 AgentError。"""
    if isinstance(value, bool) or value is None:
        raise AgentError(f"参数 {field} 必须是整数")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise AgentError(f"参数 {field} 必须是整数") from exc


def _as_cell(value, field: str) -> tuple[int, int]:
    """把参数强制转成坐标 (x, y)。"""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise AgentError(f"参数 {field} 必须是 [x, y] 两个整数")
    return _as_int(value[0], f"{field}.x"), _as_int(value[1], f"{field}.y")


def _resolve_goal(args: dict, engine) -> tuple[int, int]:
    """
    解析目标：既支持直接给坐标，也支持"第 N 号巡检点"（V2.3.1）。

    :param args: {'goal': [x,y]} 或 {'goal_index': n}。
    :param engine: 仿真引擎，用于读取地图上的巡检点列表。
    :return: 目标坐标 (x, y)。
    :raises AgentError: 序号越界或缺少参数。
    """
    if args.get("goal_index") is not None:
        index = _as_int(args["goal_index"], "goal_index")
        goals = engine.map.goals
        if not 1 <= index <= len(goals):
            raise AgentError(
                f"没有第 {index} 号巡检点（当前共 {len(goals)} 个，序号从 1 开始）"
            )
        goal = goals[index - 1]
        return int(goal[0]), int(goal[1])
    return _as_cell(args.get("goal"), "goal")


def validate_call(tool: str, args: dict, engine) -> dict:
    """
    执行前校验工具与参数（白名单 + schema + 业务语义）。

    :param tool: 工具名。
    :param args: 模型/解析器给出的参数。
    :param engine: 仿真引擎，用于读取地图、电量与机器人位置。
    :return: 规范化后的参数。
    :raises AgentError: 任一校验不通过。
    """
    if tool not in TOOL_SPECS:
        raise AgentError(f"不支持的动作：{tool}")
    if not isinstance(args, dict):
        raise AgentError("参数格式必须是 JSON 对象")

    map_data = engine.map
    robot = (engine.x, engine.y)
    if tool in ("status", "stop_patrol", "go_charge", "reset"):
        return {}

    if tool == "move":
        dx = _as_int(args.get("dx", 0), "dx")
        dy = _as_int(args.get("dy", 0), "dy")
        if dx not in (-1, 0, 1) or dy not in (-1, 0, 1):
            raise AgentError("移动步长只能是 -1、0 或 1")
        if dx == 0 and dy == 0:
            raise AgentError("移动步长不能同时为 0")
        if engine.mode == MODE_EMPTY:
            raise AgentError("电量耗尽，无法移动；请先复位或搬回起点")
        target = (robot[0] + dx, robot[1] + dy)
        if not map_data.in_bounds(*target):
            raise AgentError(f"目标格 [{target[0]}, {target[1]}] 在地图之外")
        if not map_data.is_free(*target):
            raise AgentError(f"目标格 [{target[0]}, {target[1]}] 是障碍或屏障，无法移动")
        return {"dx": dx, "dy": dy}

    if tool == "plan_route":
        goal = _resolve_goal(args, engine)
        if not map_data.in_bounds(*goal):
            raise AgentError(f"目标点 [{goal[0]}, {goal[1]}] 在地图之外")
        if map_data.grid[goal[1]][goal[0]] == CELL_BARRIER:
            raise AgentError(f"目标点 [{goal[0]}, {goal[1]}] 是固定屏障，无法到达")
        return {"goal": list(goal)}

    if tool == "start_patrol":
        if args.get("goal_index") is not None:
            goal = _resolve_goal(args, engine)
            if not map_data.is_free(*goal):
                raise AgentError(f"巡检点 [{goal[0]}, {goal[1]}] 是障碍或屏障")
            return {"goals": [list(goal)]}
        raw_goals = args.get("goals")
        if raw_goals in (None, [], {}):
            return {}
        if not isinstance(raw_goals, list):
            raise AgentError("巡检点必须是坐标数组")
        if len(raw_goals) > config.settings.agent_max_goals:
            raise AgentError(f"一次最多下发 {config.settings.agent_max_goals} 个巡检点")
        goals: list[list[int]] = []
        for item in raw_goals:
            cell = _as_cell(item, "goals")
            if not map_data.in_bounds(*cell):
                raise AgentError(f"巡检点 [{cell[0]}, {cell[1]}] 在地图之外")
            if not map_data.is_free(*cell):
                raise AgentError(f"巡检点 [{cell[0]}, {cell[1]}] 是障碍或屏障")
            goals.append(list(cell))
        return {"goals": goals}

    if tool == "clear_obstacle":
        cell = _as_cell(args.get("cell"), "cell")
        if not map_data.in_bounds(*cell):
            raise AgentError(f"目标格 [{cell[0]}, {cell[1]}] 在地图之外")
        value = map_data.grid[cell[1]][cell[0]]
        if value == CELL_BARRIER:
            raise AgentError(f"[{cell[0]}, {cell[1]}] 是固定屏障，机器人无法清除")
        if value not in CLEARABLE_CELLS:
            raise AgentError(f"[{cell[0]}, {cell[1]}] 不是障碍物，无需清除")
        cost = config.settings.material_costs.get(value, config.settings.clear_obstacle_cost)
        if engine.battery + 1e-9 < cost:
            raise AgentError(
                f"电量不足（当前 {engine.battery:.1f}%），清除{MATERIAL_LABELS.get(value, '障碍')}需要 {cost:.0f}%"
            )
        return {"cell": list(cell)}

    if tool == "set_cell":
        x = _as_int(args.get("x"), "x")
        y = _as_int(args.get("y"), "y")
        value = _as_int(args.get("value", 0), "value")
        if value not in (0, 1, 2, 3, 4):
            raise AgentError("格子取值只能是 0（空闲）、1（石头）、2（固定屏障）、3（沙子）、4（金刚石）")
        if not map_data.in_bounds(x, y):
            raise AgentError(f"坐标 [{x}, {y}] 在地图之外")
        if map_data.is_boundary(x, y):
            raise AgentError("最外环是地图边界，不能编辑")
        if value != 0 and ((x, y) == map_data.start or (x, y) == map_data.charge_point or (x, y) in map_data.goals):
            raise AgentError("起点 / 充电点 / 巡检点不能设为障碍或屏障")
        if (x, y) == robot:
            raise AgentError("机器人所在的格子不能编辑")
        return {"x": x, "y": y, "value": value}

    if tool == "new_map":
        width = _as_int(args.get("width"), "width")
        height = _as_int(args.get("height"), "height")
        if not (config.settings.min_map_size <= width <= config.settings.max_map_size):
            raise AgentError(f"地图宽度需在 {config.settings.min_map_size}~{config.settings.max_map_size} 之间")
        if not (config.settings.min_map_size <= height <= config.settings.max_map_size):
            raise AgentError(f"地图高度需在 {config.settings.min_map_size}~{config.settings.max_map_size} 之间")
        return {"width": width, "height": height}

    raise AgentError(f"不支持的动作：{tool}")


# ---------------------------------------------------------------------------
# 大模型（可选，本地 Ollama）
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """你是一个二维巡检机器人的指令解析器。用户会用中文下达一条指令，
你只能从下面的工具白名单里选择一个，并输出严格 JSON（不要解释、不要 Markdown）：

{specs}

输出格式：
{{"tool": "工具名", "args": {{...}}}}

规则：
- 坐标写作 [x, y]，x 是列、y 是行；
- 没有合适的工具时输出 {{"tool": "none", "args": {{}}}}；
- 不要发明工具名或参数名。
"""


def _build_system_prompt() -> str:
    """把工具白名单渲染进系统提示词。"""
    lines = []
    for name, spec in TOOL_SPECS.items():
        lines.append(f"- {name}: {spec['description']}；参数：{json.dumps(spec['args'], ensure_ascii=False)}")
    return _SYSTEM_PROMPT.format(specs="\n".join(lines))


def _call_ollama(text: str, timeout: float) -> dict:
    """
    调用本地 Ollama 的 /api/chat，要求返回 JSON 工具调用。

    只允许 127.0.0.1 之类的本地地址（默认值），不做任意外部转发；调用失败抛异常，
    由上层回退到规则解析。

    :param text: 用户指令。
    :param timeout: 超时秒数。
    :return: {'tool': str, 'args': dict}。
    """
    url = config.settings.agent_ollama_url.rstrip("/") + "/api/chat"
    payload = {
        "model": config.settings.agent_ollama_model,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0, "num_predict": 200},
        "messages": [
            {"role": "system", "content": _build_system_prompt()},
            {"role": "user", "content": text},
        ],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - 地址来自配置
        body = json.loads(response.read().decode("utf-8"))
    content = (body.get("message") or {}).get("content", "")
    parsed = json.loads(content)
    tool = parsed.get("tool")
    args = parsed.get("args") or {}
    if tool in (None, "none"):
        return {"tool": None, "args": {}, "reason": "模型没有给出可用工具"}
    return {"tool": tool, "args": args, "reason": "本地模型解析"}


# ---------------------------------------------------------------------------
# Agent 服务
# ---------------------------------------------------------------------------


class AgentService:
    """自然语言指令服务：解析 → 校验 → （必要时确认）→ 执行 → 汇报。"""

    def __init__(self, engine, notify=None) -> None:
        """
        :param engine: 仿真引擎实例。
        :param notify: 可选回调，用于把执行结果广播到 WebSocket。
        """
        self._engine = engine
        self._notify = notify

    # ---------- 解析 ----------

    def _heading(self) -> tuple[int, int]:
        """机器人当前朝向对应的单位步长（四舍五入到 8 方向之一）。"""
        return self._engine.heading_step()

    async def _understand(self, text: str) -> tuple[dict, str]:
        """
        把自然语言解析成工具调用。优先本地大模型（若启用），失败则规则兜底。

        :param text: 用户指令。
        :return: (调用字典, 来源标记)。
        """
        if config.settings.agent_llm_enabled:
            try:
                parsed = await asyncio.to_thread(
                    _call_ollama, text, config.settings.agent_llm_timeout_s
                )
                return parsed, "llm"
            except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as exc:
                logger.warning("本地模型解析失败（%s），回退到规则解析", exc)
                parsed = parse_rules(text, self._heading())
                return parsed, "rule-fallback"
        return parse_rules(text, self._heading()), "rule"

    # ---------- 执行 ----------

    def _execute(self, tool: str, args: dict) -> tuple[bool, str, dict | None]:
        """
        在引擎上执行一个已通过校验的工具调用。

        :param tool: 工具名。
        :param args: 已校验的参数。
        :return: (是否成功, 面向用户的说明, 结果数据)。
        """
        engine = self._engine

        if tool == "status":
            patrol = engine.get_patrol_status()
            message = (
                f"当前位于 [{engine.x}, {engine.y}]，朝向 {engine.theta:.2f} rad，"
                f"电量 {engine.battery:.1f}%，模式「{MODE_LABELS.get(engine.mode, engine.mode)}」，"
                f"巡检进度 {patrol['completed']}/{patrol['total']}。"
            )
            if engine.pending:
                message += f" 另有 {len(engine.pending)} 处待清障。"
            return True, message, {"state": engine.state_dict()["data"], "patrol": patrol}

        if tool == "plan_route":
            goal = args["goal"]
            plan = engine.plan_route(goal)
            if not plan["path"]:
                suggestion = plan.get("suggestion")
                if suggestion:
                    return (
                        False,
                        f"到 [{goal[0]}, {goal[1]}] 没有可行路线；建议清除 "
                        f"[{suggestion[0]}, {suggestion[1]}] 后重试。",
                        plan,
                    )
                return False, f"到 [{goal[0]}, {goal[1]}] 没有可行路线。", plan
            steps = max(0, len(plan["path"]) - 1)
            if not plan["enough"]:
                message = (
                    f"路线已生成：{steps} 步，预计耗电 {plan['total_cost']:.1f}%，"
                    f"但电量只有 {plan['battery']:.1f}%，途中需要先充电。"
                )
            else:
                message = (
                    f"路线已生成：到 [{goal[0]}, {goal[1]}] 共 {steps} 步，"
                    f"预计耗电 {plan['total_cost']:.1f}%"
                    f"（其中清障 {plan['clear_cost']:.1f}%，共 {len(plan['clearable'])} 处）。"
                )
            return True, message, plan

        if tool == "start_patrol":
            status = engine.start_patrol(args.get("goals"))
            if not status.get("running"):
                return False, "当前无法开始巡检（可能电量为空或没有巡检点）。", status
            if status.get("total") == 1 and status.get("current_goal"):
                goal = status["current_goal"]
                message = f"已出发前往巡检点 [{goal[0]}, {goal[1]}]（单点任务）。"
            else:
                message = f"自动巡检已启动，共 {status['total']} 个巡检点，机器人开始逐点前往。"
            return True, message, status

        if tool == "stop_patrol":
            status = engine.stop_patrol()
            return True, "已停止自动巡检，机器人回到手动模式。", status

        if tool == "go_charge":
            payload = engine.go_charge()
            if engine.mode != "charging":
                return False, "当前无法返航充电（充电点不可达或已电量耗尽）。", payload
            steps = max(0, len(engine.path) - 1)
            return True, f"正在返回充电点，预计 {steps} 步到达。", payload

        if tool == "move":
            engine.move(args["dx"], args["dy"])
            direction = _direction_label(args["dx"], args["dy"])
            return (
                engine.mode != "blocked",
                f"已{direction}移动一格，当前位于 [{engine.x}, {engine.y}]，"
                f"电量 {engine.battery:.1f}%。",
                engine.state_dict()["data"],
            )

        if tool == "clear_obstacle":
            cell = args["cell"]
            value = engine.map.grid[cell[1]][cell[0]]
            cost = config.settings.material_costs.get(value, config.settings.clear_obstacle_cost)
            payload = engine.clear_obstacle_at(cell)
            if engine.map.grid[cell[1]][cell[0]] != 0:
                return False, f"清除 [{cell[0]}, {cell[1]}] 失败（可能电量不足）。", payload
            return (
                True,
                f"已清除{MATERIAL_LABELS.get(value, '障碍')} [{cell[0]}, {cell[1]}]，扣除 {cost:.0f}% 电量，"
                f"剩余 {engine.battery:.1f}%。",
                payload,
            )

        if tool == "set_cell":
            payload = engine.set_cell(args["x"], args["y"], args["value"])
            label = {0: "空闲", 1: "石头", 2: "固定屏障", 3: "沙子", 4: "金刚石"}[args["value"]]
            return True, f"已把 [{args['x']}, {args['y']}] 设为{label}。", payload

        if tool == "reset":
            engine.reset(keep_trail=False)
            return True, "机器人已复位到起点，电量恢复 100%。", engine.state_dict()["data"]

        if tool == "new_map":
            engine.new_map(args["width"], args["height"])
            return (
                True,
                f"已新建 {args['width']}×{args['height']} 的空白地图（仅保留边界墙）。",
                engine.get_map(),
            )

        return False, f"不支持的动作：{tool}", None

    # ---------- 对外入口 ----------

    async def handle(self, text: str, confirm: bool = False) -> dict:
        """
        处理一条自然语言指令。

        :param text: 用户输入。
        :param confirm: 破坏性操作的二次确认标记。
        :return: 结构化结果（前端直接渲染）。
        """
        started = time.perf_counter()
        cleaned = (text or "").strip()
        if not cleaned:
            return self._payload("", False, None, {}, "rule", False, False, False, "指令不能为空。", None, started)
        if len(cleaned) > 200:
            return self._payload(
                cleaned, False, None, {}, "rule", False, False, False,
                "指令太长了（最多 200 字）。", None, started,
            )

        parsed, source = await self._understand(cleaned)
        tool = parsed.get("tool")
        args = parsed.get("args") or {}
        if not tool:
            return self._payload(
                cleaned, False, None, {}, source, False, False, False,
                "没听懂这句指令。可以试试「去 5,5 巡检」「回充电点」「把 3,4 的障碍清掉」或「现在状态怎么样」。",
                None, started,
            )

        try:
            safe_args = validate_call(tool, args, self._engine)
        except AgentError as exc:
            logger.info("Agent 参数校验未通过：%s %s（%s）", tool, args, exc)
            return self._payload(
                cleaned, True, tool, args, source, False, False, False, str(exc), None, started
            )

        if tool in DESTRUCTIVE_TOOLS and not confirm:
            message = f"这条指令会修改现场状态：{TOOL_SPECS[tool]['description']}（{_describe_args(tool, safe_args)}）。确认执行吗？"
            return self._payload(
                cleaned, True, tool, safe_args, source, False, True, False, message, None, started
            )

        ok, message, result = self._execute(tool, safe_args)
        payload = self._payload(
            cleaned, True, tool, safe_args, source, ok, False, ok, message, result, started
        )
        log = logger.info if ok else logger.warning
        log("Agent 执行 %s %s → %s", tool, safe_args, message)
        if self._notify:
            try:
                self._notify({"type": "agent", "data": payload})
            except Exception:  # noqa: BLE001 - 广播失败不影响命令本身
                logger.exception("Agent 结果广播失败")
        return payload

    @staticmethod
    def _payload(
        text: str,
        understood: bool,
        tool: str | None,
        args: dict,
        source: str,
        executed: bool,
        need_confirm: bool,
        ok: bool,
        message: str,
        result,
        started: float,
    ) -> dict:
        """统一构造返回体，保证前后端字段一致。"""
        return {
            "text": text,
            "understood": understood,
            "tool": tool,
            "args": args,
            "source": source,
            "executed": executed,
            "need_confirm": need_confirm,
            "ok": ok,
            "message": message,
            "result": result,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        }

    @staticmethod
    def describe_tools() -> list[dict]:
        """返回工具清单（供 GET /api/v1/agent/tools 与前端示例）。"""
        return [
            {"name": name, **spec}
            for name, spec in TOOL_SPECS.items()
        ]


def _direction_label(dx: int, dy: int) -> str:
    """把步长翻译成中文方向。"""
    if dx > 0:
        return "向右"
    if dx < 0:
        return "向左"
    if dy > 0:
        return "向下"
    if dy < 0:
        return "向上"
    return "原地"


def _describe_args(tool: str, args: dict) -> str:
    """把参数渲染成一句中文，用于确认提示。"""
    if tool == "clear_obstacle":
        cell = args["cell"]
        return f"清除 [{cell[0]}, {cell[1]}] 的障碍（按材质扣电）"
    if tool == "set_cell":
        label = {0: "空闲", 1: "石头", 2: "固定屏障", 3: "沙子", 4: "金刚石"}[args["value"]]
        return f"把 [{args['x']}, {args['y']}] 设为{label}"
    if tool == "new_map":
        return f"新建 {args['width']}×{args['height']} 空白地图"
    if tool == "reset":
        return "复位机器人并恢复满电"
    return json.dumps(args, ensure_ascii=False)
