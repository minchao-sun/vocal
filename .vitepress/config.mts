import fs from 'node:fs'
import path from 'node:path'
import { defineConfig, type DefaultTheme } from 'vitepress'
import type MarkdownIt from 'markdown-it'
import cjkFriendly from 'markdown-it-cjk-friendly'
import { getBooks, rootDir } from './books'

const repoUrl = 'https://github.com/minchao-sun/vocal'
const books = getBooks()

/**
 * Vue only bundles asset URLs that start with `.`, `~` or `@`, so raw HTML like
 * `<img src="images/a.png">` (which renders fine on GitHub) would otherwise be
 * left as an unresolved path. Prefix such URLs with `./`.
 */
function relativeMediaSrc(md: MarkdownIt) {
  const pattern =
    /(<(?:img|audio|video|source|track)\b[^>]*?\s(?:src|poster)\s*=\s*["'])(?![./~@#]|[a-z][a-z0-9+.-]*:)/gi
  const fix = (s: string) => s.replace(pattern, '$1./')
  md.core.ruler.push('relative_media_src', (state) => {
    for (const token of state.tokens) {
      if (token.type === 'html_block') token.content = fix(token.content)
      for (const child of token.children ?? []) {
        if (child.type === 'html_inline') child.content = fix(child.content)
      }
    }
  })
}

/**
 * Relative links to folders or non-Markdown files work on GitHub but have no
 * page on the site; point them at the repository on GitHub instead.
 */
function repoFileLinks(md: MarkdownIt) {
  md.core.ruler.push('repo_file_links', (state) => {
    const sourceFile: string | undefined = state.env.path
    if (!sourceFile) return
    for (const token of state.tokens) {
      for (const child of token.children ?? []) {
        if (child.type !== 'link_open') continue
        const href = child.attrGet('href')
        if (!href || /^([a-z][a-z0-9+.-]*:|#|\/)/i.test(href)) continue
        const target = decodeURI(href.split(/[?#]/)[0])
        if (/\.(md|html)$/i.test(target)) continue
        const abs = path.resolve(path.dirname(sourceFile), target)
        if (!fs.existsSync(abs)) continue
        const rel = path.relative(rootDir, abs).split(path.sep).join('/')
        const kind = fs.statSync(abs).isDirectory() ? 'tree' : 'blob'
        child.attrSet('href', `${repoUrl}/${kind}/main/${encodeURI(rel)}`)
      }
    }
  })
}

const sidebar: DefaultTheme.SidebarMulti = Object.fromEntries(
  books.map((book) => [
    book.link,
    [
      {
        text: book.title,
        link: book.link,
        items: book.chapters.map((c) => ({ text: c.title, link: c.link }))
      }
    ]
  ])
)

export default defineConfig({
  lang: 'zh-CN',
  title: '音乐学习书架',
  description: '音乐相关的学习用书',
  base: '/vocal/',
  cleanUrls: true,
  lastUpdated: true,

  srcExclude: ['README.md'],
  rewrites: { ':book/README.md': ':book/index.md' },

  markdown: {
    // cjkFriendly: lets `**粗体（注）**后文` close after CJK punctuation.
    config: (md) => md.use(cjkFriendly).use(relativeMediaSrc).use(repoFileLinks)
  },

  vue: {
    template: {
      transformAssetUrls: {
        img: ['src'],
        image: ['xlink:href', 'href'],
        use: ['xlink:href', 'href'],
        video: ['src', 'poster'],
        audio: ['src'],
        source: ['src'],
        track: ['src']
      }
    }
  },

  themeConfig: {
    nav: [
      { text: '书架', link: '/' },
      ...books.map((b) => ({ text: b.title, link: b.link, activeMatch: `^${b.link}` })),
      { text: '博客', link: 'https://minchao-sun.github.io/' }
    ],
    sidebar,
    outline: { level: [2, 3], label: '本页目录' },
    docFooter: { prev: '上一篇', next: '下一篇' },
    lastUpdated: { text: '最后更新' },
    editLink: {
      pattern: `${repoUrl}/edit/main/:path`,
      text: '在 GitHub 上编辑此页'
    },
    socialLinks: [{ icon: 'github', link: repoUrl }],
    returnToTopLabel: '回到顶部',
    sidebarMenuLabel: '目录',
    darkModeSwitchLabel: '深色模式',
    lightModeSwitchTitle: '切换到浅色模式',
    darkModeSwitchTitle: '切换到深色模式',
    notFound: { title: '页面不存在', quote: '这一页可能已被移动或删除。', linkText: '回到书架' },

    search: {
      provider: 'local',
      options: {
        miniSearch: {
          options: {
            // Serialized to the browser, so it must not reference outer variables.
            tokenize(text: string) {
              const segmenter = new Intl.Segmenter('zh-CN', { granularity: 'word' })
              return Array.from(segmenter.segment(text))
                .filter((s) => s.isWordLike)
                .map((s) => s.segment)
            }
          }
        },
        translations: {
          button: { buttonText: '搜索', buttonAriaLabel: '搜索' },
          modal: {
            displayDetails: '显示详细列表',
            resetButtonTitle: '清除查询',
            backButtonTitle: '关闭搜索',
            noResultsText: '没有找到相关结果',
            footer: {
              selectText: '选择',
              navigateText: '切换',
              closeText: '关闭'
            }
          }
        }
      }
    }
  }
})
