/**
 * 模块功能：机器人自定义形象（本地存储）
 * 作者：智能巡检机器人二维仿真系统 V1.0 前端开发组
 * 日期：2026-10-24
 * 版本：V1.0
 *
 * 用户上传的机器人形象以 data URL 形式存放在 localStorage，
 * 不经过任何服务器，刷新后依然生效；"恢复默认"即清除存储。
 */

/** localStorage 键名。 */
const STORAGE_KEY = 'irm_robot_avatar_v1'

/** 图片大小上限（字节），超出会拖垮 localStorage 配额。 */
const MAX_SIZE_BYTES = 2 * 1024 * 1024

/**
 * 读取本地保存的机器人形象。
 *
 * @returns {string|null} data URL 或 null。
 */
export function getAvatar() {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

/**
 * 保存机器人形象。
 *
 * @param {string} dataUrl - 图片 data URL。
 * @returns {boolean} 是否保存成功（超额时失败）。
 */
export function setAvatar(dataUrl) {
  try {
    localStorage.setItem(STORAGE_KEY, dataUrl)
    return true
  } catch (error) {
    console.warn('机器人形象保存失败（可能超出本地存储配额）：', error)
    return false
  }
}

/**
 * 清除机器人形象，恢复默认矢量绘制。
 */
export function clearAvatar() {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // localStorage 不可用时忽略
  }
}

/**
 * 读取图片文件并校验类型与大小，解析为 data URL。
 *
 * @param {File} file - 用户选择的图片文件。
 * @returns {Promise<string>} data URL；校验失败时抛出 Error。
 */
export function readAvatarFile(file) {
  return new Promise((resolve, reject) => {
    if (!file.type || !file.type.startsWith('image/')) {
      reject(new Error('请选择图片文件（PNG / JPG / SVG 等）'))
      return
    }
    if (file.size > MAX_SIZE_BYTES) {
      reject(new Error('图片大小不能超过 2MB'))
      return
    }
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = () => reject(new Error('图片读取失败，请重试'))
    reader.readAsDataURL(file)
  })
}
