import { defineLoader } from 'vitepress'
import { getBooks, type Book } from '../books'

declare const data: Book[]
export { data }

export default defineLoader({
  watch: ['../../*/README.md', '../../*/[0-9]*.md'],
  load: () => getBooks()
})
