<script setup lang="ts">
import { h, onMounted, ref } from 'vue'
import { useMessage, NTag, NButton, NPopconfirm } from 'naive-ui'
import { useI18n } from 'vue-i18n'
import { listTasks, deleteTask } from '../api'

const message = useMessage()
const { t } = useI18n()

const loading = ref(false)
const rows = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const playingId = ref<string | null>(null)

const columns = [
  {
    title: t('common.status'), key: 'status', width: 90,
    render: (r: any) => h(NTag, {
      size: 'small',
      type: r.status === 'completed' ? 'success' : r.status === 'failed' ? 'error' : r.status === 'running' ? 'info' : 'default'
    }, { default: () => t(`status.${r.status}`) })
  },
  { title: t('history.voice'), key: 'voice_name', width: 120 },
  {
    title: t('history.textPreview'), key: 'text', ellipsis: { tooltip: true }
  },
  { title: t('common.language'), key: 'language', width: 80 },
  { title: t('history.duration'), key: 'duration_sec', width: 90, render: (r: any) => r.duration_sec ? `${r.duration_sec}${t('common.seconds')}` : '-' },
  { title: t('history.elapsed'), key: 'elapsed_sec', width: 90, render: (r: any) => r.elapsed_sec ? `${r.elapsed_sec}${t('common.seconds')}` : '-' },
  { title: t('common.createdAt'), key: 'created_at', width: 160 },
  {
    title: t('common.actions'), key: 'actions', width: 180,
    render: (r: any) => h('div', { style: 'display:flex;gap:6px' }, [
      r.status === 'completed'
        ? h(NButton, { size: 'tiny', onClick: () => onPlay(r) }, { default: () => t('common.play') })
        : h(NButton, { size: 'tiny', disabled: true }, { default: () => t('common.play') }),
      r.status === 'completed'
        ? h(NButton, { size: 'tiny', tag: 'a', href: r.audio_url, download: true }, { default: () => t('common.download') })
        : null,
      h(NPopconfirm, { onPositiveClick: () => onDelete(r) }, {
        trigger: () => h(NButton, { size: 'tiny', type: 'error', ghost: true }, { default: () => t('common.delete') }),
        default: () => t('history.deleteConfirm')
      })
    ])
  }
]

async function load() {
  loading.value = true
  try {
    const res = await listTasks({ page: page.value, page_size: pageSize.value })
    rows.value = res.data.items || []
    total.value = res.data.total || 0
  } finally { loading.value = false }
}

onMounted(load)

function onPlay(r: any) {
  if (!r.audio_url) return
  playingId.value = r.id
  const audio = new Audio(r.audio_url)
  audio.onended = () => (playingId.value = null)
  audio.play()
}

async function onDelete(r: any) {
  try {
    await deleteTask(r.id)
    message.success(t('voices.deleted'))
    await load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || 'Error')
  }
}
</script>

<template>
  <div class="page-wrap">
    <div class="flex-between mb-16">
      <div>
        <div class="section-title">{{ t('history.title') }}</div>
        <div style="color:#64748b; font-size:13px">{{ t('history.desc') }}</div>
      </div>
      <n-button @click="load" :loading="loading">{{ t('common.refresh') }}</n-button>
    </div>

    <n-data-table
      :columns="columns"
      :data="rows"
      :loading="loading"
      :pagination="{
        page, pageSize, itemCount: total,
        onChange: (p: number) => { page = p; load() }
      }"
      row-key="id"
      bordered
    />
  </div>
</template>
