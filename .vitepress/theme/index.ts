import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'
import Bookshelf from './Bookshelf.vue'
import './custom.css'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('Bookshelf', Bookshelf)
  }
} satisfies Theme
