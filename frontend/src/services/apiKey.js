/**
 * 模块功能：操作密钥的本地存取
 * 作者：智能巡检机器人二维仿真系统 V2.2.0 前端开发组
 * 日期：2026-10-26
 * 版本：V2.2.0
 *
 * 密钥只存在 sessionStorage：关闭标签页即失效，不写入 localStorage、
 * 也不参与构建（VITE_* 变量会被打进公开 JS，绝不能放这里的值）。
 */

const STORAGE_KEY = 'irm_operator_key_v1'

/**
 * 读取当前操作密钥。
 *
 * @returns {string} 密钥，未设置时为空串。
 */
export function getApiKey() {
  try {
    return sessionStorage.getItem(STORAGE_KEY) || ''
  } catch {
    return ''
  }
}

/**
 * 保存操作密钥。
 *
 * @param {string} key - 密钥明文。
 */
export function setApiKey(key) {
  try {
    if (key) sessionStorage.setItem(STORAGE_KEY, key)
    else sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    // 隐私模式禁用 sessionStorage 时静默降级为"本次不保存"
  }
}

/** 清除操作密钥（退出操作模式）。 */
export function clearApiKey() {
  setApiKey('')
}

/**
 * 生成带密钥的请求头。
 *
 * @param {Object} [extra] - 额外请求头。
 * @returns {Object} 合并后的请求头。
 */
export function authHeaders(extra = {}) {
  const key = getApiKey()
  return key ? { ...extra, 'X-API-Key': key } : { ...extra }
}
