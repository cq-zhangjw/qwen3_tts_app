<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useMessage } from 'naive-ui'
import { useI18n } from 'vue-i18n'
import { listVoices, deleteVoice, getSystemInfo } from '../api'

const message = useMessage()
const { t } = useI18n()

const loading = ref(false)
const filter = ref('all')
const keyword = ref('')
const presetVoices = ref<any[]>([])
const customVoices = ref<any[]>([])
const playingId = ref<string | null>(null)

async function load() {
  loading.value = true
  try {
    const sys = await getSystemInfo()
    presetVoices.value = (sys.data.preset_voices || []).map((v: any) => ({
      ...v, type: 'preset', status: 'ready'
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

function onPreview(v: any) {
  const url = v.audio_url || (v.type === 'preset' ? '' : '')
  if (!url) { message.info(t('voices.empty')); return }
  playingId.value = v.id
  const audio = new Audio(url)
  audio.onended = () => (playingId.value = null)
  audio.play()
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
</script>

<template>
  <div class="page-wrap">
    <div class="flex-between mb-16">
      <div>
        <div class="section-title">{{ t('voices.title') }}</div>
        <div style="color:#64748b; font-size:13px">{{ t('voices.desc') }}</div>
      </div>
      <n-button @click="load" :loading="loading">{{ t('common.refresh') }}</n-button>
    </div>

    <div class="flex gap-8 mb-16" style="flex-wrap:wrap">
      <n-radio-group v-model:value="filter" size="small">
        <n-radio-button value="all">{{ t('voices.filterAll') }}</n-radio-button>
        <n-radio-button value="preset">{{ t('voices.filterPreset') }}</n-radio-button>
        <n-radio-button value="clone">{{ t('voices.filterClone') }}</n-radio-button>
        <n-radio-button value="design">{{ t('voices.filterDesign') }}</n-radio-button>
      </n-radio-group>
      <n-input v-model:value="keyword" :placeholder="t('voices.searchPlaceholder')" style="width:220px" size="small" />
    </div>

    <n-spin :show="loading">
      <n-grid :cols="24" :responsive="['screen']" :x-gap="16" :y-gap="16">
        <n-gi v-for="v in allVoices" :key="v.id" :span="24" :span-tablet="12" :span-laptop="8" :span-mobile="24">
          <n-card class="voice-card" size="small" bordered>
            <div style="display:flex; gap:12px; align-items:flex-start">
              <n-avatar
                :size="46"
                :color="v.type === 'preset' ? '#6366f1' : v.type === 'clone' ? '#22c55e' : '#a855f7'"
                round
              >{{ (v.name || '?').slice(0, 1) }}</n-avatar>
              <div style="flex:1; min-width:0">
                <div class="flex-between">
                  <strong>{{ v.name }}</strong>
                  <n-tag size="tiny" :type="typeTagType(v.type)">{{ t(`voiceType.${v.type}`) }}</n-tag>
                </div>
                <div style="color:#64748b; font-size:12px; margin-top:4px">
                  {{ v.description || v.instruct || v.speaker || '' }}
                </div>
                <n-tag v-if="v.status === 'processing'" size="tiny" type="warning" class="mt-16">{{ t('status.processing') }}</n-tag>
                <n-tag v-else-if="v.status === 'failed'" size="tiny" type="error">{{ t('status.failed') }}</n-tag>
              </div>
            </div>
            <div class="flex gap-8 mt-16">
              <n-button size="tiny" :disabled="!v.audio_url || v.status !== 'ready'" @click="onPreview(v)">
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
</template>
