<script setup>
import { ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { getWordbook, listWordbookWords } from '../../api/wordbooks'
import AudioButton from '../../components/AudioButton.vue'
import PagePagination from '../../components/PagePagination.vue'
import { getErrorMessage } from '../../utils/errors'

const PAGE_SIZE = 15
const route = useRoute()
const wordbook = ref(null)
const words = ref([])
const total = ref(0)
const page = ref(1)
const mastery = ref('')
const isLoading = ref(true)
const errorMessage = ref('')

const masteryOptions = [
  { value: '', label: '全部掌握度' },
  { value: '0', label: '新词' },
  { value: '1', label: '学习中' },
  { value: '2', label: '已掌握' },
]

function masteryLabel(level) {
  if (level === 2) return '已掌握'
  if (level === 1) return '学习中'
  return '新词'
}

function masteryClass(level) {
  if (level === 2) return 'mastery-dot--mastered'
  if (level === 1) return 'mastery-dot--learning'
  return 'mastery-dot--new'
}

async function loadPage() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const wordbookId = Number(route.params.id)
    const [detail, wordList] = await Promise.all([
      getWordbook(wordbookId),
      listWordbookWords(wordbookId, {
        page: page.value,
        pageSize: PAGE_SIZE,
        mastery: mastery.value === '' ? null : Number(mastery.value),
      }),
    ])
    wordbook.value = detail
    words.value = wordList.items || []
    total.value = wordList.total || 0
  } catch (error) {
    errorMessage.value = getErrorMessage(error, '这本词书暂时无法打开，请稍后再试。')
  } finally {
    isLoading.value = false
  }
}

watch([() => route.params.id, page, mastery], loadPage, { immediate: true })
</script>

<template>
  <div class="app-page">
    <RouterLink class="back-link" to="/wordbooks">← 返回词书架</RouterLink>

    <div v-if="isLoading" class="skeleton-stack" aria-label="正在载入词书">
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
    </div>

    <section v-else-if="errorMessage" class="state-panel">
      <h1 class="state-title">这一页暂时读不到</h1>
      <p class="state-copy">{{ errorMessage }}</p>
      <button class="secondary-button" type="button" @click="loadPage">重新载入</button>
    </section>

    <template v-else>
      <header class="detail-header">
        <div class="detail-header__copy">
          <p class="eyebrow">{{ wordbook?.level || '综合词书' }} · WORD LIST</p>
          <h1 class="page-title">{{ wordbook?.name }}</h1>
          <p class="page-copy">
            {{ wordbook?.description || '把每一个词看清楚，再凭记忆写下来。' }}
          </p>
        </div>
        <div class="detail-header__action">
          <span>{{ wordbook?.word_count || 0 }} 个单词</span>
          <RouterLink
            class="primary-button"
            :to="{ name: 'practice', query: { wordbook_id: wordbook?.id } }"
          >
            开始默写
          </RouterLink>
        </div>
      </header>

      <section class="word-section">
        <div class="word-section__toolbar">
          <div>
            <p class="eyebrow">VOCABULARY INDEX</p>
            <h2 class="section-title">单词目录</h2>
          </div>
          <label class="mastery-filter">
            <span class="sr-only">按掌握度筛选</span>
            <select v-model="mastery" class="field-input" @change="page = 1">
              <option v-for="option in masteryOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </label>
        </div>

        <div v-if="!words.length" class="state-panel state-panel--center">
          <h3 class="state-title">这一页还没有词</h3>
          <p class="state-copy">换个掌握度筛选看看，或者先开始一轮默写。</p>
        </div>

        <div v-else class="data-table-wrap">
          <table class="data-table word-table">
            <thead>
              <tr>
                <th>单词</th>
                <th>音标</th>
                <th>释义</th>
                <th>掌握度</th>
                <th>发音</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="word in words" :key="word.id">
                <td class="word-table__spelling">{{ word.spelling }}</td>
                <td class="word-table__phonetic">
                  {{ word.phonetic_uk || word.phonetic_us || '—' }}
                </td>
                <td>
                  <span v-if="word.part_of_speech" class="part-of-speech">
                    {{ word.part_of_speech }}
                  </span>
                  {{ word.meaning_cn || '释义待补充' }}
                </td>
                <td>
                  <span class="mastery">
                    <i class="mastery-dot" :class="masteryClass(word.mastery_level)"></i>
                    {{ masteryLabel(word.mastery_level) }}
                  </span>
                </td>
                <td>
                  <AudioButton
                    :word-id="word.id"
                    :audio-url="word.audio_url || ''"
                    :label="word.spelling"
                    compact
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <PagePagination
          v-if="total > PAGE_SIZE"
          v-model:page="page"
          :page-size="PAGE_SIZE"
          :total="total"
        />
      </section>
    </template>
  </div>
</template>

<style scoped>
.back-link {
  display: inline-block;
  margin-bottom: 30px;
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

.detail-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 34px;
  padding-bottom: 30px;
  border-bottom: 1px solid var(--color-border);
}

.detail-header__copy {
  max-width: 680px;
}

.detail-header__action {
  display: flex;
  align-items: center;
  gap: 18px;
  white-space: nowrap;
}

.detail-header__action span {
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

.detail-header__action a:hover {
  text-decoration: none;
}

.word-section {
  padding-top: 34px;
}

.word-section__toolbar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 16px;
}

.mastery-filter {
  width: 168px;
}

.word-table__spelling {
  color: var(--color-primary);
  font-family: var(--font-family-title);
  font-size: var(--font-size-md);
  font-weight: 600;
}

.word-table__phonetic {
  color: var(--color-disabled);
  font-family: var(--font-family-title);
}

.part-of-speech {
  margin-right: 5px;
  color: var(--color-accent);
  font-size: var(--font-size-xs);
  font-style: italic;
}

.mastery {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--color-disabled);
  font-size: var(--font-size-xs);
}

.mastery-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--color-border);
}

.mastery-dot--new {
  background: var(--color-disabled);
}

.mastery-dot--learning {
  background: var(--color-accent);
}

.mastery-dot--mastered {
  background: var(--color-success);
}

@media (max-width: 720px) {
  .detail-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .word-section__toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .mastery-filter {
    width: 100%;
  }
}
</style>
