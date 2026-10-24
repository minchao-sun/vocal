import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export interface Chapter {
  title: string
  /** Route relative to the site root, without base, e.g. `/vocal-theory/01-导论` */
  link: string
}

export interface Book {
  dir: string
  title: string
  description: string
  link: string
  chapters: Chapter[]
}

export const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

const CHAPTER_FILE = /^\d+.*\.md$/

const read = (file: string) => fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, '')

function readTitle(file: string, fallback: string): string {
  const match = read(file).match(/^#\s+(.+?)\s*$/m)
  return match ? match[1] : fallback
}

/** First plain paragraph after the H1, used as the book blurb on the shelf. */
function readDescription(file: string): string {
  const lines = read(file).split(/\r?\n/)
  const start = lines.findIndex((l) => /^#\s/.test(l))
  const paragraph: string[] = []
  for (const line of lines.slice(start + 1)) {
    const text = line.trim()
    if (!text) {
      if (paragraph.length) break
      continue
    }
    if (/^([#|>\-*<]|```)/.test(text)) break
    paragraph.push(text)
  }
  return paragraph.join('').replace(/\*\*|__|`/g, '')
}

export function getBooks(): Book[] {
  return fs
    .readdirSync(rootDir, { withFileTypes: true })
    .filter((d) => d.isDirectory() && !/^[._]/.test(d.name) && d.name !== 'node_modules')
    .filter((d) => fs.existsSync(path.join(rootDir, d.name, 'README.md')))
    .map((d) => {
      const bookDir = path.join(rootDir, d.name)
      const readme = path.join(bookDir, 'README.md')
      const chapters = fs
        .readdirSync(bookDir)
        .filter((f) => CHAPTER_FILE.test(f))
        .sort((a, b) => a.localeCompare(b, 'en', { numeric: true }))
        .map((f) => ({
          title: readTitle(path.join(bookDir, f), f.replace(/\.md$/, '')),
          link: `/${d.name}/${f.replace(/\.md$/, '')}`
        }))
      return {
        dir: d.name,
        title: readTitle(readme, d.name),
        description: readDescription(readme),
        link: `/${d.name}/`,
        chapters
      }
    })
    .sort((a, b) => a.dir.localeCompare(b.dir))
}
