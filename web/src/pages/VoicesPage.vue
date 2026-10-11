<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useMessage } from 'naive-ui'
import { useI18n } from 'vue-i18n'
import { listVoices, deleteVoice, getSystemInfo, previewVoice } from '../api'

const message = useMessage()
const { t, locale } = useI18n()

function localLabel(v: any) {
  return v[`label_${locale.value}`] || v.label_zh || v.name || v.id
}

const loading = ref(false)
const filter = ref('all')
const keyword = ref('')
const presetVoices = ref<any[]>([])
const customVoices = ref<any[]>([])
const playingId = ref<string | null>(null)
const previewingId = ref<string | null>(null)

async function load() {
  loading.value = true
  try {
    const sys = await getSystemInfo()
    presetVoices.value = (sys.data.preset_voices || []).map((v: any) => ({
      ...v, id: v.id, name: localLabel(v), type: 'preset',
      status: 'ready', speaker: v.speaker
    }))
    const res = await listVoices({ type: filter.value === 'all' ? undefined : filter.value })
    customVoices.value = res.data || []
  } finally { loading.value = false }
}

onMounted(load)

const allVoices = computed(() => {
  let rows = filter.value === 'all'
    ? [...customVoices.value, ...presetVoices.value]
    : customVoices.value
  if (keyword.value) rows = rows.filter((v: any) => v.name.toLowerCase().includes(keyword.value.toLowerCase()))
  return rows
})

async function onPreview(v: any) {
  if (playingId.value === v.id) return
  previewingId.value = v.id
  try {
    let url = v.audio_url
    if (!url) {
      const res = await previewVoice(v.id)
      url = res.data.audio_url
    }
    playingId.value = v.id
    const audio = new Audio(url)
    audio.onended = () => (playingId.value = null)
    audio.play()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || 'Error')
  } finally {
    previewingId.value = null
  }
}

async function onDelete(v: any) {
  try {
    await deleteVoice(v.id)
    message.success(t('voices.deleted'))
    await load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || 'Error')
  }
}

function typeTagType(type: string) {
  return type === 'preset' ? 'info' : type === 'clone' ? 'success' : 'warning'
}

const PREVIEW_SAMPLES: Record<string, string> = {
  zh: '你好，很高兴认识你，欢迎来到我的小世界。',
  en: 'Hello, nice to meet you. Welcome to my little world.',
  ja: 'こんにちは、はじめまして。よろしくお願いします。',
}
function previewText(v: any) {
  const lang = v.language === 'ja' ? 'ja' : v.language === 'en' ? 'en' : 'zh'
  return PREVIEW_SAMPLES[lang] || PREVIEW_SAMPLES.zh
}
</script>

<template>
  <div style="height: calc(100vh - 56px); display:flex; flex-direction:column; padding:20px 20px 0; box-sizing:border-box">
    <div class="flex-between mb-16" style="flex-shrink:0">
      <div>
        <div class="section-title">{{ t('voices.title') }}</div>
        <div style="color:#64748b; font-size:13px">{{ t('voices.desc') }}</div>
      </div>
    </div>

    <div class="flex gap-8 mb-16" style="flex-wrap:wrap; flex-shrink:0">
      <n-radio-group v-model:value="filter" size="small">
        <n-radio-button value="all">{{ t('voices.filterAll') }}</n-radio-button>
        <n-radio-button value="preset">{{ t('voices.filterPreset') }}</n-radio-button>
        <n-radio-button value="clone">{{ t('voices.filterClone') }}</n-radio-button>
        <n-radio-button value="design">{{ t('voices.filterDesign') }}</n-radio-button>
      </n-radio-group>
      <n-input v-model:value="keyword" :placeholder="t('voices.searchPlaceholder')" style="width:220px" size="small" />
    </div>

    <!-- Only this area scrolls -->
    <div style="flex:1; overflow-y:auto; padding-bottom:20px">
      <n-spin :show="loading">
        <n-grid :cols="24" :responsive="['screen']" :x-gap="16" :y-gap="16">
          <n-gi v-for="v in allVoices" :key="v.id" :span="24" :span-tablet="12" :span-laptop="8" :span-mobile="24">
            <n-card class="voice-card" size="small" bordered>
              <div style="display:flex; gap:12px; align-items:flex-start">
                <n-avatar :size="46" round
                  :color="v.type === 'preset' ? '#6366f1' : v.type === 'clone' ? '#22c55e' : '#a855f7'">
                  {{ (v.name || '?').slice(0, 1) }}
                </n-avatar>
                <div style="flex:1; min-width:0">
                  <div style="display:flex; justify-content:space-between; align-items:center">
                    <strong>{{ v.name }}</strong>
                    <n-space :size="4">
                      <n-tag size="tiny" bordered>{{ v.language === 'ja' ? '日本語' : v.language === 'en' ? 'EN' : v.language === 'auto' ? 'Auto' : '中文' }}</n-tag>
                      <n-tag size="tiny" :type="typeTagType(v.type)">{{ t(`voiceType.${v.type}`) }}</n-tag>
                    </n-space>
                  </div>
                  <div style="color:#64748b; font-size:12px; margin-top:4px">
                    {{ v.description || v.instruct || v.speaker || '' }}
                  </div>
                  <div style="color:#94a3b8; font-size:11px; margin-top:6px; padding:6px 8px; background:#f8fafc; border-radius:6px; font-style:italic">
                    📢 {{ previewText(v) }}
                  </div>
                </div>
              </div>
              <div class="flex gap-8 mt-16">
                <n-button size="tiny" :loading="previewingId === v.id" @click="onPreview(v)">
                  {{ playingId === v.id ? '…' : t('common.preview') }}
                </n-button>
                <n-popconfirm v-if="v.type !== 'preset'" @positive-click="onDelete(v)">
                  <template #trigger>
                    <n-button size="tiny" type="error" ghost>{{ t('common.delete') }}</n-button>
                  </template>
                  {{ t('common.confirm') }}?
                </n-popconfirm>
              </div>
            </n-card>
          </n-gi>
        </n-grid>
        <n-empty v-if="!allVoices.length" class="mt-16" :description="t('voices.empty')" />
      </n-spin>
    </div>
  </div>
</template>
