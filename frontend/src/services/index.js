// 数据服务层统一导出与数据源工厂
// 界面组件只通过 RobotService 接口访问数据，永远不直接触碰数据来源；
// 切换数据实现（本地仿真 / 后端）时组件零改动。

import { RobotService } from './robotService.js'
import { SimulatedService } from './simulatedService.js'
import { RemoteService } from './remoteService.js'
import { astar } from './astar.js'

export { RobotService, SimulatedService, RemoteService, astar }

// 解析后端基地址：依次看 URL ?backend=、全局变量、构建期环境变量。
// 三者皆无则返回空串，由工厂回退到本地仿真器（静态部署保持离线版）。
export function resolveBackendUrl() {
  if (import.meta.env && import.meta.env.VITE_BACKEND_SAME_ORIGIN === 'true') {
    if (typeof window !== 'undefined') return window.location.origin
  }
  if (typeof window !== 'undefined') {
    const fromQuery = new URLSearchParams(window.location.search).get('backend')
    if (fromQuery) return fromQuery
    if (window.__BACKEND_URL__) return window.__BACKEND_URL__
  }
  if (import.meta.env && import.meta.env.VITE_BACKEND_URL) {
    return import.meta.env.VITE_BACKEND_URL
  }
  return ''
}

// 带 ?backend= 时返回 RemoteService（接入 FastAPI），否则 SimulatedService（离线仿真）。
export function createRobotService() {
  const backendUrl = resolveBackendUrl()
  if (backendUrl) return new RemoteService(backendUrl)
  return new SimulatedService()
}
