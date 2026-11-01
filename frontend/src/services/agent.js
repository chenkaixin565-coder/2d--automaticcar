/**
 * 模块功能：前端 Agent 指令层（自然语言 → 白名单工具）
 * 作者：智能巡检机器人二维仿真系统 V2.3.0 前端开发组
 * 日期：2026-10-30
 * 版本：V2.3.0
 *
 * 离线模式（SimulatedService）下没有后端，本模块承担与后端
 * `backend/app/services/agent.py` 等价的职责：中文规则解析 → 参数校验 →
 * 执行 → 汇报。工具集合、校验规则与返回字段刻意与后端保持一致，
 * 这样同一句话在"离线仿真"和"后端服务"两种模式下行为相同。
 *
 * 在线模式（RemoteService）不走这里：整句直接提交给后端，由后端的大模型/
 * 规则解析器处理，前端只负责展示返回结果。
 */

/** 工具白名单：与后端 TOOL_SPECS 同名同参。 */
export const TOOL_SPECS = {
  status: { description: '查询机器人当前位置、电量、模式与巡检进度', destructive: false },
  plan_route: { description: '规划到目标点的路线（只预览，不移动）', destructive: false },
  start_patrol: { description: '开始自动巡检', destructive: false },
  stop_patrol: { description: '停止当前自动巡检任务', destructive: false },
  go_charge: { description: '让机器人返回充电点', destructive: false },
  move: { description: '手动移动一格', destructive: false },
  clear_obstacle: { description: '清除指定格子的障碍（扣 5% 电量）', destructive: true },
  set_cell: { description: '编辑地图格子（空闲 / 障碍 / 屏障）', destructive: true },
  reset: { description: '复位机器人到起点并恢复满电', destructive: true },
  new_map: { description: '新建一张空白地图', destructive: true },
}

/** 需要二次确认的破坏性工具。 */
const DESTRUCTIVE_TOOLS = new Set(
  Object.entries(TOOL_SPECS)
    .filter(([, spec]) => spec.destructive)
    .map(([name]) => name)
)

/** 模式中文名。 */
const MODE_LABELS = {
  manual: '手动',
  patrol: '自动巡检',
  charging: '返航充电',
  blocked: '受阻',
  empty: '电量耗尽',
}

const COORD_RE = /(\d{1,3})\s*[,，、xX×]\s*(\d{1,3})/g
const GRID_RE = /(\d{1,2})\s*[xX×*]\s*(\d{1,2})/

const STOP_WORDS = ['停止', '停下', '停住', '别走', '别动', '取消巡检', '停止巡检', 'stop']
const STATUS_WORDS = ['状态', '电量', '多少电', '在哪', '位置', '报告', '情况', '怎么样']
const CHARGE_WORDS = ['充电', '回充', '返航', '回血', '补电']
const CLEAR_WORDS = ['清除', '清掉', '清障', '拆掉', '拆了', '铲掉', '移走', '去掉', '删掉']
const PATROL_WORDS = ['巡检', '巡逻', '巡查', 'patrol']
const PLAN_WORDS = ['规划', '路线', '预览', '怎么走', '路径', '导航']
const RESET_WORDS = ['复位', '重置', '回起点', '回到起点']
const NEW_MAP_WORDS = ['新建地图', '新建一张', '新地图', '重新开始画']
const FORWARD_WORDS = ['前进', '往前', '向前走', '前进一格']
const BACKWARD_WORDS = ['后退', '往后', '向后走']
const UP_WORDS = ['向上', '往上', '上移', '上面']
const DOWN_WORDS = ['向下', '往下', '下移', '下面']
const LEFT_WORDS = ['向左', '往左', '左移', '左边']
const RIGHT_WORDS = ['向右', '往右', '右移', '右边']
const SET_WORDS = ['设成', '设为', '设置为', '改成', '标记为']
const BARRIER_WORDS = ['屏障', '固定墙', '永久墙']
const OBSTACLE_WORDS = ['障碍', '墙', '阻挡']
const EMPTY_WORDS = ['空闲', '空地', '通行', '清空']

/** Agent 参数校验失败。 */
export class AgentError extends Error {}

/**
 * 归一化输入：全角数字/标点转半角，压缩空白。
 *
 * @param {string} text - 原始输入。
 * @returns {string} 归一化后的文本。
 */
function normalize(text) {
  return String(text || '')
    .replace(/[０-９]/g, (ch) => String.fromCharCode(ch.charCodeAt(0) - 0xfee0))
    .replace(/[，、；：！？（）]/g, (ch) => ({ '，': ',', '、': ',', '；': ';', '：': ':', '！': '!', '？': '?', '（': '(', '）': ')' }[ch]))
    .replace(/\s+/g, ' ')
    .trim()
}

/**
 * 是否包含任一关键词。
 *
 * @param {string} text - 文本。
 * @param {string[]} words - 关键词。
 * @returns {boolean} 命中与否。
 */
function has(text, words) {
  return words.some((word) => text.includes(word))
}

/**
 * 提取全部坐标对。
 *
 * @param {string} text - 文本。
 * @returns {number[][]} [[x, y], ...]
 */
function extractCoords(text) {
  const result = []
  COORD_RE.lastIndex = 0
  let match = COORD_RE.exec(text)
  while (match) {
    result.push([Number(match[1]), Number(match[2])])
    match = COORD_RE.exec(text)
  }
  return result
}

/**
 * 内置中文规则解析（与后端 parse_rules 同一套意图与优先级）。
 *
 * @param {string} text - 用户输入。
 * @param {number[]} [heading=[1, 0]] - 当前朝向对应的单位步长。
 * @returns {{tool: string|null, args: Object, reason: string}} 解析结果。
 */
export function parseRules(text, heading = [1, 0]) {
  const normalized = normalize(text)
  const coords = extractCoords(normalized)

  if (has(normalized, STOP_WORDS)) return { tool: 'stop_patrol', args: {}, reason: '停止巡检' }
  if (has(normalized, STATUS_WORDS)) return { tool: 'status', args: {}, reason: '查询状态' }
  if (has(normalized, CHARGE_WORDS)) return { tool: 'go_charge', args: {}, reason: '返回充电点' }
  if (has(normalized, CLEAR_WORDS) && coords.length > 0) {
    return { tool: 'clear_obstacle', args: { cell: coords[0] }, reason: '清除障碍' }
  }
  if (has(normalized, PATROL_WORDS)) {
    return { tool: 'start_patrol', args: coords.length ? { goals: coords } : {}, reason: '开始巡检' }
  }
  if (has(normalized, PLAN_WORDS) && coords.length > 0) {
    return { tool: 'plan_route', args: { goal: coords[0] }, reason: '规划路线' }
  }
  if (has(normalized, RESET_WORDS)) return { tool: 'reset', args: {}, reason: '复位' }

  const gridMatch = GRID_RE.exec(normalized)
  if (has(normalized, NEW_MAP_WORDS) && gridMatch) {
    return {
      tool: 'new_map',
      args: { width: Number(gridMatch[1]), height: Number(gridMatch[2]) },
      reason: '新建地图',
    }
  }

  if (has(normalized, SET_WORDS) && coords.length > 0) {
    let value = 0
    if (has(normalized, BARRIER_WORDS)) value = 2
    else if (has(normalized, OBSTACLE_WORDS)) value = 1
    else if (has(normalized, EMPTY_WORDS)) value = 0
    return {
      tool: 'set_cell',
      args: { x: coords[0][0], y: coords[0][1], value },
      reason: '编辑地图格子',
    }
  }

  if (has(normalized, FORWARD_WORDS)) {
    return { tool: 'move', args: { dx: heading[0], dy: heading[1] }, reason: '前进' }
  }
  if (has(normalized, BACKWARD_WORDS)) {
    return { tool: 'move', args: { dx: -heading[0], dy: -heading[1] }, reason: '后退' }
  }
  if (has(normalized, UP_WORDS)) return { tool: 'move', args: { dx: 0, dy: -1 }, reason: '向上' }
  if (has(normalized, DOWN_WORDS)) return { tool: 'move', args: { dx: 0, dy: 1 }, reason: '向下' }
  if (has(normalized, LEFT_WORDS)) return { tool: 'move', args: { dx: -1, dy: 0 }, reason: '向左' }
  if (has(normalized, RIGHT_WORDS)) return { tool: 'move', args: { dx: 1, dy: 0 }, reason: '向右' }

  if (coords.length > 0 && has(normalized, ['去', '到', '前往', '走'])) {
    return { tool: 'plan_route', args: { goal: coords[0] }, reason: '规划路线' }
  }

  return { tool: null, args: {}, reason: '没有识别出可执行的指令' }
}

/**
 * 把参数强制转为整数。
 *
 * @param {*} value - 原值。
 * @param {string} field - 字段名。
 * @returns {number} 整数。
 */
function asInt(value, field) {
  const number = Number(value)
  if (!Number.isFinite(number) || !Number.isInteger(number)) {
    throw new AgentError(`参数 ${field} 必须是整数`)
  }
  return number
}

/**
 * 把参数强制转为坐标。
 *
 * @param {*} value - 原值。
 * @param {string} field - 字段名。
 * @returns {number[]} [x, y]
 */
function asCell(value, field) {
  if (!Array.isArray(value) || value.length !== 2) {
    throw new AgentError(`参数 ${field} 必须是 [x, y] 两个整数`)
  }
  return [asInt(value[0], `${field}.x`), asInt(value[1], `${field}.y`)]
}

/**
 * 执行前校验工具与参数（白名单 + schema + 业务语义）。
 *
 * @param {string} tool - 工具名。
 * @param {Object} args - 参数。
 * @param {{map: Object, state: Object, limits: Object}} context - 地图、机器人状态与规则常量。
 * @returns {Object} 规范化后的参数。
 */
export function validateCall(tool, args, context) {
  const { map, state, limits } = context
  if (!TOOL_SPECS[tool]) throw new AgentError(`不支持的动作：${tool}`)
  if (!args || typeof args !== 'object' || Array.isArray(args)) {
    throw new AgentError('参数格式必须是 JSON 对象')
  }
  if (['status', 'stop_patrol', 'go_charge', 'reset'].includes(tool)) return {}

  const inBounds = (x, y) => x >= 0 && x < map.width && y >= 0 && y < map.height
  const isFree = (x, y) => inBounds(x, y) && map.grid[y][x] === 0
  const isBoundary = (x, y) => x === 0 || y === 0 || x === map.width - 1 || y === map.height - 1

  if (tool === 'move') {
    const dx = asInt(args.dx ?? 0, 'dx')
    const dy = asInt(args.dy ?? 0, 'dy')
    if (![-1, 0, 1].includes(dx) || ![-1, 0, 1].includes(dy)) {
      throw new AgentError('移动步长只能是 -1、0 或 1')
    }
    if (dx === 0 && dy === 0) throw new AgentError('移动步长不能同时为 0')
    if (state.mode === 'empty') throw new AgentError('电量耗尽，无法移动；请先复位或搬回起点')
    const target = [state.x + dx, state.y + dy]
    if (!inBounds(target[0], target[1])) {
      throw new AgentError(`目标格 [${target[0]}, ${target[1]}] 在地图之外`)
    }
    if (!isFree(target[0], target[1])) {
      throw new AgentError(`目标格 [${target[0]}, ${target[1]}] 是障碍或屏障，无法移动`)
    }
    return { dx, dy }
  }

  if (tool === 'plan_route') {
    const goal = asCell(args.goal, 'goal')
    if (!inBounds(goal[0], goal[1])) throw new AgentError(`目标点 [${goal[0]}, ${goal[1]}] 在地图之外`)
    if (map.grid[goal[1]][goal[0]] === 2) {
      throw new AgentError(`目标点 [${goal[0]}, ${goal[1]}] 是固定屏障，无法到达`)
    }
    return { goal }
  }

  if (tool === 'start_patrol') {
    const raw = args.goals
    if (raw === undefined || raw === null || (Array.isArray(raw) && raw.length === 0)) return {}
    if (!Array.isArray(raw)) throw new AgentError('巡检点必须是坐标数组')
    if (raw.length > limits.maxGoals) throw new AgentError(`一次最多下发 ${limits.maxGoals} 个巡检点`)
    const goals = raw.map((item) => {
      const cell = asCell(item, 'goals')
      if (!inBounds(cell[0], cell[1])) throw new AgentError(`巡检点 [${cell[0]}, ${cell[1]}] 在地图之外`)
      if (!isFree(cell[0], cell[1])) throw new AgentError(`巡检点 [${cell[0]}, ${cell[1]}] 是障碍或屏障`)
      return cell
    })
    return { goals }
  }

  if (tool === 'clear_obstacle') {
    const cell = asCell(args.cell, 'cell')
    if (!inBounds(cell[0], cell[1])) throw new AgentError(`目标格 [${cell[0]}, ${cell[1]}] 在地图之外`)
    const value = map.grid[cell[1]][cell[0]]
    if (value === 2) throw new AgentError(`[${cell[0]}, ${cell[1]}] 是固定屏障，机器人无法清除`)
    if (value !== 1) throw new AgentError(`[${cell[0]}, ${cell[1]}] 不是障碍物，无需清除`)
    if (state.battery < limits.clearCost) {
      throw new AgentError(
        `电量不足（当前 ${state.battery.toFixed(1)}%），清除一处需要 ${limits.clearCost.toFixed(0)}%`
      )
    }
    return { cell }
  }

  if (tool === 'set_cell') {
    const x = asInt(args.x, 'x')
    const y = asInt(args.y, 'y')
    const value = asInt(args.value ?? 0, 'value')
    if (![0, 1, 2].includes(value)) throw new AgentError('格子取值只能是 0（空闲）、1（障碍）或 2（固定屏障）')
    if (!inBounds(x, y)) throw new AgentError(`坐标 [${x}, ${y}] 在地图之外`)
    if (isBoundary(x, y)) throw new AgentError('最外环是地图边界，不能编辑')
    const isKeyCell =
      (x === map.start[0] && y === map.start[1]) ||
      (x === map.charge_point[0] && y === map.charge_point[1]) ||
      map.goals.some((goal) => goal[0] === x && goal[1] === y)
    if (value !== 0 && isKeyCell) throw new AgentError('起点 / 充电点 / 巡检点不能设为障碍或屏障')
    if (value !== 0 && x === state.x && y === state.y) throw new AgentError('机器人所在的格子不能编辑')
    return { x, y, value }
  }

  if (tool === 'new_map') {
    const width = asInt(args.width, 'width')
    const height = asInt(args.height, 'height')
    if (width < limits.minMap || width > limits.maxMap) {
      throw new AgentError(`地图宽度需在 ${limits.minMap}~${limits.maxMap} 之间`)
    }
    if (height < limits.minMap || height > limits.maxMap) {
      throw new AgentError(`地图高度需在 ${limits.minMap}~${limits.maxMap} 之间`)
    }
    return { width, height }
  }

  throw new AgentError(`不支持的动作：${tool}`)
}

/**
 * 在本地仿真服务上执行一次已校验的工具调用。
 *
 * @param {string} tool - 工具名。
 * @param {Object} args - 已校验参数。
 * @param {Object} service - SimulatedService 实例。
 * @param {Object} map - 当前地图。
 * @returns {Promise<{ok: boolean, message: string, result: *}>} 执行结果。
 */
async function executeTool(tool, args, service, map) {
  const state = service.getState()

  if (tool === 'status') {
    const patrol = service.getPatrolStatus()
    let message =
      `当前位于 [${state.x}, ${state.y}]，朝向 ${state.theta.toFixed(2)} rad，` +
      `电量 ${state.battery.toFixed(1)}%，模式「${MODE_LABELS[state.mode] || state.mode}」，` +
      `巡检进度 ${patrol.completed || 0}/${patrol.total || 0}。`
    const pending = service.getPending()
    if (pending && pending.length) message += ` 另有 ${pending.length} 处待清障。`
    return { ok: true, message, result: { state, patrol } }
  }

  if (tool === 'plan_route') {
    const plan = service.planRoute(args.goal)
    if (!plan || !plan.path || plan.path.length === 0) {
      return { ok: false, message: `到 [${args.goal[0]}, ${args.goal[1]}] 没有可行路线。`, result: plan }
    }
    const steps = Math.max(0, plan.path.length - 1)
    const message = plan.enough
      ? `路线已生成：到 [${args.goal[0]}, ${args.goal[1]}] 共 ${steps} 步，预计耗电 ${plan.total_cost.toFixed(1)}%（其中清障 ${plan.clear_cost.toFixed(1)}%，共 ${plan.clearable.length} 处）。`
      : `路线已生成：${steps} 步，预计耗电 ${plan.total_cost.toFixed(1)}%，但电量只有 ${plan.battery.toFixed(1)}%，途中需要先充电。`
    return { ok: true, message, result: plan }
  }

  if (tool === 'start_patrol') {
    service.startPatrol(args.goals)
    const status = service.getPatrolStatus()
    if (!status.running) return { ok: false, message: '当前无法开始巡检（可能电量为空或没有巡检点）。', result: status }
    return { ok: true, message: `自动巡检已启动，共 ${status.total} 个巡检点，机器人开始逐点前往。`, result: status }
  }

  if (tool === 'stop_patrol') {
    service.stopPatrol()
    return { ok: true, message: '已停止自动巡检，机器人回到手动模式。', result: service.getPatrolStatus() }
  }

  if (tool === 'go_charge') {
    service.goCharge()
    const after = service.getState()
    if (after.mode !== 'charging') {
      return { ok: false, message: '当前无法返航充电（充电点不可达或已电量耗尽）。', result: after }
    }
    return { ok: true, message: `正在返回充电点 [${map.charge_point[0]}, ${map.charge_point[1]}]。`, result: after }
  }

  if (tool === 'move') {
    service.move(args.dx, args.dy)
    const after = service.getState()
    const label = args.dx > 0 ? '向右' : args.dx < 0 ? '向左' : args.dy > 0 ? '向下' : '向上'
    return {
      ok: after.mode !== 'blocked',
      message: `已${label}移动一格，当前位于 [${after.x}, ${after.y}]，电量 ${after.battery.toFixed(1)}%。`,
      result: after,
    }
  }

  if (tool === 'clear_obstacle') {
    service.clearObstacleAt(args.cell)
    const after = service.getState()
    const cleared = map.grid[args.cell[1]][args.cell[0]] === 0
    if (!cleared) return { ok: false, message: `清除 [${args.cell[0]}, ${args.cell[1]}] 失败（可能电量不足）。`, result: after }
    return {
      ok: true,
      message: `已清除 [${args.cell[0]}, ${args.cell[1]}] 的障碍，扣除 5% 电量，剩余 ${after.battery.toFixed(1)}%。`,
      result: after,
    }
  }

  if (tool === 'set_cell') {
    service.setCell(args.x, args.y, args.value)
    const label = { 0: '空闲', 1: '障碍', 2: '固定屏障' }[args.value]
    return { ok: true, message: `已把 [${args.x}, ${args.y}] 设为${label}。`, result: needMapSnapshot(map) }
  }

  if (tool === 'reset') {
    service.reset()
    const after = service.getState()
    return { ok: true, message: '机器人已复位到起点，电量恢复 100%。', result: after }
  }

  if (tool === 'new_map') {
    service.newMap(args.width, args.height)
    return {
      ok: true,
      message: `已新建 ${args.width}×${args.height} 的空白地图（仅保留边界墙）。`,
      result: needMapSnapshot(map),
    }
  }

  return { ok: false, message: `不支持的动作：${tool}`, result: null }
}

/**
 * 地图快照（只保留展示需要的字段）。
 *
 * @param {Object} map - 地图对象。
 * @returns {Object} 快照。
 */
function needMapSnapshot(map) {
  return { width: map.width, height: map.height, start: [...map.start], goals: map.goals.map((g) => [...g]) }
}

/**
 * 生成与后端 `AgentService._payload` 字段一致的返回体。
 *
 * @param {Object} options - 字段集合。
 * @returns {Object} 统一返回体。
 */
function payload(options) {
  return {
    text: options.text || '',
    understood: Boolean(options.understood),
    tool: options.tool || null,
    args: options.args || {},
    source: options.source || 'rule',
    executed: Boolean(options.executed),
    need_confirm: Boolean(options.needConfirm),
    ok: Boolean(options.ok),
    message: options.message || '',
    result: options.result === undefined ? null : options.result,
    latency_ms: options.latencyMs || 0,
  }
}

/**
 * 描述参数，用于二次确认提示。
 *
 * @param {string} tool - 工具名。
 * @param {Object} args - 参数。
 * @returns {string} 中文描述。
 */
export function describeArgs(tool, args) {
  if (tool === 'clear_obstacle') {
    return `清除 [${args.cell[0]}, ${args.cell[1]}] 的障碍，扣 5% 电量`
  }
  if (tool === 'set_cell') {
    const label = { 0: '空闲', 1: '障碍', 2: '固定屏障' }[args.value]
    return `把 [${args.x}, ${args.y}] 设为${label}`
  }
  if (tool === 'new_map') return `新建 ${args.width}×${args.height} 空白地图`
  if (tool === 'reset') return '复位机器人并恢复满电'
  return JSON.stringify(args)
}

/**
 * 处理一条自然语言指令（离线模式入口）。
 *
 * @param {string} text - 用户输入。
 * @param {Object} options - { confirm, service, map, limits }
 * @returns {Promise<Object>} 与后端一致的返回体。
 */
export async function handleAgentCommand(text, options = {}) {
  const started = typeof performance !== 'undefined' ? performance.now() : Date.now()
  const elapsed = () => {
    const now = typeof performance !== 'undefined' ? performance.now() : Date.now()
    return Math.round((now - started) * 10) / 10
  }
  const { confirm = false, service, map, limits } = options
  const cleaned = String(text || '').trim()

  if (!cleaned) {
    return payload({ text: cleaned, message: '指令不能为空。', latencyMs: elapsed() })
  }
  if (cleaned.length > 200) {
    return payload({ text: cleaned, message: '指令太长了（最多 200 字）。', latencyMs: elapsed() })
  }

  const state = service.getState()
  const facing = state.theta === undefined ? [1, 0] : headingStep(state.theta)
  const parsed = parseRules(cleaned, facing)
  const tool = parsed.tool
  if (!tool) {
    return payload({
      text: cleaned,
      message:
        '没听懂这句指令。可以试试「去 5,5 巡检」「回充电点」「把 3,4 的障碍清掉」或「现在状态怎么样」。',
      latencyMs: elapsed(),
    })
  }

  let safeArgs
  try {
    safeArgs = validateCall(tool, parsed.args, { map, state, limits })
  } catch (error) {
    if (!(error instanceof AgentError)) throw error
    return payload({
      text: cleaned,
      understood: true,
      tool,
      args: parsed.args,
      message: error.message,
      latencyMs: elapsed(),
    })
  }

  if (DESTRUCTIVE_TOOLS.has(tool) && !confirm) {
    return payload({
      text: cleaned,
      understood: true,
      tool,
      args: safeArgs,
      needConfirm: true,
      message: `这条指令会修改现场状态：${TOOL_SPECS[tool].description}（${describeArgs(tool, safeArgs)}）。确认执行吗？`,
      latencyMs: elapsed(),
    })
  }

  const outcome = await executeTool(tool, safeArgs, service, map)
  return payload({
    text: cleaned,
    understood: true,
    tool,
    args: safeArgs,
    executed: outcome.ok,
    ok: outcome.ok,
    message: outcome.message,
    result: outcome.result,
    latencyMs: elapsed(),
  })
}

/**
 * 把朝向角量化为单位步长（四邻域），用于解释"前进/后退"。
 *
 * @param {number} theta - 朝向弧度。
 * @returns {number[]} 单位步长 [dx, dy]。
 */
function headingStep(theta) {
  const normalized = ((theta % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI)
  const half = Math.PI / 4
  if (normalized < half || normalized >= 7 * half) return [1, 0]
  if (normalized < 3 * half) return [0, 1]
  if (normalized < 5 * half) return [-1, 0]
  return [0, -1]
}
