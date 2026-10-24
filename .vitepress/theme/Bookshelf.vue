<script setup lang="ts">
import { withBase } from 'vitepress'
import { data as books } from './books.data'
</script>

<template>
  <div class="bookshelf">
    <a v-for="book in books" :key="book.dir" class="book" :href="withBase(book.link)">
      <h2 class="book-title">{{ book.title }}</h2>
      <p class="book-desc">{{ book.description }}</p>
      <p class="book-meta">已写 {{ book.chapters.length }} 篇</p>
    </a>
  </div>
</template>

<style scoped>
.bookshelf {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 20px;
  margin-top: 24px;
}

.book {
  display: flex;
  flex-direction: column;
  padding: 24px;
  border: 1px solid var(--vp-c-divider);
  border-left: 6px solid var(--vp-c-brand-1);
  border-radius: 8px;
  background: var(--vp-c-bg-soft);
  color: inherit;
  text-decoration: none;
  transition: border-color 0.2s, transform 0.2s;
}

.book:hover {
  border-color: var(--vp-c-brand-1);
  transform: translateY(-2px);
}

.book-title {
  margin: 0 0 8px;
  padding: 0;
  border: none;
  font-size: 20px;
  font-weight: 600;
}

.book-desc {
  flex: 1;
  margin: 0;
  color: var(--vp-c-text-2);
  font-size: 14px;
  line-height: 1.7;
}

.book-meta {
  margin: 16px 0 0;
  color: var(--vp-c-text-3);
  font-size: 13px;
}
</style>
