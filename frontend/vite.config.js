import { readFileSync } from 'node:fs'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// 构建时把 package.json 的版本号写进静态资源引用（V2.3.6）
const pkg = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf-8'))

/**
 * 给 index.html 里的静态资源加版本号查询参数。
 *
 * 目的：老手机/旧浏览器缓存了上一版 JS、CSS 或图标时，会和新版本混用，
 * 出现"新旧界面交替闪烁"。加 `?v=<版本号>` 后每次发版引用路径都变，
 * 浏览器必须重新拉取。
 *
 * 只处理构建产物（./assets/xxx 与 favicon），开发服务器的 /src/main.js 不受影响。
 *
 * @returns {import('vite').Plugin} Vite 插件。
 */
function versionQueryPlugin() {
  const suffix = `?v=${pkg.version}`
  return {
    name: 'irm-version-query',
    enforce: 'post',
    transformIndexHtml(html) {
      return html
        .replace(/(src|href)="\.\/assets\/([^"?]+)"/g, `$1="./assets/$2${suffix}"`)
        .replace(/(src|href)="(?:\.\/|\/)?favicon\.svg"/g, `$1="./favicon.svg${suffix}"`)
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  base: './',
  plugins: [vue(), versionQueryPlugin()],
  // 开发服务器允许读取仓库根目录：共享规则在 ../shared 下（V2.2.0）
  server: {
    fs: { allow: ['..'] },
  },
  test: {
    environment: 'jsdom',
    globals: true,
  },
})
