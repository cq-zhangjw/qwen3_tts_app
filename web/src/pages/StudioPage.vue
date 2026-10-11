<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { useI18n } from 'vue-i18n'
import { createTask, getSystemInfo, listVoices, listTasks, getTask, deleteTask } from '../api'

const message = useMessage()
const { t, locale } = useI18n()

function localLabel(v: any) {
  return v[`label_${locale.value}`] || v.label_zh || v.name || v.id
}

const text = ref('')
const voiceId = ref('')
const language = ref('auto')
const instruct = ref('')
const submitting = ref(false)

const presetVoices = ref<any[]>([])
const customVoices = ref<any[]>([])
const tasks = ref<any[]>([])
const playingId = ref<string | null>(null)
let timer: number | null = null

const voiceOptions = computed(() => [
  {
    label: t('voices.filterPreset'),
    options: presetVoices.value.map(v => ({ label: localLabel(v), value: v.id }))
  },
  {
    label: t('voices.filterClone') + ' / ' + t('voices.filterDesign'),
    options: customVoices.value
      .filter(v => v.status === 'ready')
      .map(v => ({ label: `${v.name} [${t(`voiceType.${v.type}`)}]`, value: v.id }))
  }
])

const langOptions = computed(() => [
  { label: t('lang.zh'), value: 'zh' },
  { label: t('lang.en'), value: 'en' },
  { label: t('lang.ja'), value: 'ja' },
  { label: t('lang.auto'), value: 'auto' }
])

onMounted(async () => {
  try {
    const sys = await getSystemInfo()
    presetVoices.value = sys.data.preset_voices || []
  } catch (e) { /* ignore */ }
  await loadCustom()
  if (presetVoices.value.length) voiceId.value = presetVoices.value[0].id
  await loadTasks()
  timer = window.setInterval(pollRunning, 1500)
})

onUnmounted(() => { if (timer) window.clearInterval(timer) })

async function loadCustom() {
  try {
    const res = await listVoices()
    customVoices.value = res.data || []
  } catch (e) { /* ignore */ }
}

async function loadTasks() {
  try {
    const res = await listTasks({ page: 1, page_size: 20 })
    tasks.value = res.data.items || []
  } catch (e) { /* ignore */ }
}

function hasRunning() {
  return tasks.value.some(x => x.status === 'pending' || x.status === 'running')
}

async function pollRunning() {
  if (!hasRunning()) return
  const ids = tasks.value.filter(x => x.status === 'pending' || x.status === 'running').map(x => x.id)
  for (const id of ids) {
    try {
      const res = await getTask(id)
      const idx = tasks.value.findIndex(x => x.id === id)
      if (idx >= 0) tasks.value[idx] = res.data
    } catch (e) { /* ignore */ }
  }
}

async function onSubmit() {
  if (!text.value.trim()) { message.warning(t('studio.needText')); return }
  if (!voiceId.value) { message.warning(t('studio.needVoice')); return }
  submitting.value = true
  try {
    const res = await createTask({
      text: text.value,
      voice_id: voiceId.value,
      language: language.value,
      instruct: instruct.value || null
    })
    message.success(t('studio.submitted'))
    // immediately prepend the task so the user sees it
    const fresh = await getTask(res.data.id)
    tasks.value.unshift(fresh.data)
    text.value = ''
  } catch (e: any) {
    message.error(e?.response?.data?.detail || 'Error')
  } finally {
    submitting.value = false
  }
}

function onPlay(t: any) {
  if (!t.audio_url) return
  playingId.value = t.id
  const audio = new Audio(t.audio_url)
  audio.onended = () => (playingId.value = null)
  audio.play()
}

async function onDelete(t: any) {
  try {
    await deleteTask(t.id)
    tasks.value = tasks.value.filter(x => x.id !== t.id)
  } catch (e) { /* ignore */ }
}

function statusType(s: string) {
  return s === 'completed' ? 'success' : s === 'failed' ? 'error' : s === 'running' ? 'info' : 'default'
}
</script>

<template>
  <div class="page-wrap" style="max-width: 1400px">
    <n-grid :cols="24" :responsive="['screen']" :x-gap="16" style="align-items:start">
      <!-- Left: input form -->
      <n-gi :span="24" :span-tablet="12" :span-laptop="10" :span-mobile="24">
        <n-card bordered :title="t('studio.title')">
          <n-input v-model:value="text" type="textarea" :rows="8"
            :placeholder="t('studio.textPlaceholder')" show-count />
          <div class="mt-16" style="display:flex; gap:12px; flex-wrap:wrap">
            <n-select v-model:value="voiceId" :options="voiceOptions" style="flex:1; min-width:200px" />
            <n-select v-model:value="language" :options="langOptions" style="width:130px" />
          </div>
          <n-collapse class="mt-16">
            <n-collapse-item :title="t('studio.advanced')" name="adv">
              <n-input v-model:value="instruct" :placeholder="t('studio.instructPlaceholder')" />
            </n-collapse-item>
          </n-collapse>
          <n-button type="primary" class="mt-16" :loading="submitting" block @click="onSubmit">
            {{ t('studio.synthesize') }}
          </n-button>
        </n-card>
      </n-gi>

      <!-- Right: task list (merged history) -->
      <n-gi :span="24" :span-tablet="12" :span-laptop="14" :span-mobile="24">
        <n-card bordered :title="t('history.title')" class="mb-16">
          <template #header-extra>
            <n-button size="tiny" quaternary @click="loadTasks">{{ t('common.refresh') }}</n-button>
          </template>
          <n-grid v-if="tasks.length" :cols="2" :responsive="['screen']" :x-gap="12" :y-gap="12">
            <n-gi v-for="task of tasks" :key="task.id" :span="2" :span-tablet="2" :span-laptop="1" :span-mobile="2">
              <n-card size="small" :bordered="true" style="height:100%">
                <div style="display:flex; justify-content:space-between; align-items:center; gap:6px">
                  <div style="display:flex; align-items:center; gap:6px; min-width:0">
                    <n-tag size="tiny" :type="statusType(task.status)">{{ t(`status.${task.status}`) }}</n-tag>
                    <strong style="font-size:13px">{{ task.voice_name }}</strong>
                  </div>
                  <div style="display:flex; gap:4px; flex-shrink:0">
                    <n-button size="tiny" quaternary :disabled="task.status !== 'completed'" @click="onPlay(task)">
                      {{ playingId === task.id ? '…' : t('common.play') }}
                    </n-button>
                    <n-button v-if="task.status === 'completed'" size="tiny" quaternary tag="a" :href="task.audio_url" download>
                      {{ t('common.download') }}
                    </n-button>
                    <n-popconfirm @positive-click="onDelete(task)">
                      <template #trigger>
                        <n-button size="tiny" quaternary type="error">{{ t('common.delete') }}</n-button>
                      </template>
                      {{ t('common.confirm') }}?
                    </n-popconfirm>
                  </div>
                </div>
                <div style="color:#64748b; font-size:12px; margin-top:6px; overflow:hidden; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical">
                  {{ task.text }}
                </div>
                <n-progress v-if="task.status === 'running' || task.status === 'pending'"
                  :percentage="task.progress || 0" :show-indicator="false" height="4" class="mt-16" />
                <div v-if="task.status === 'completed'" style="color:#94a3b8; font-size:11px; margin-top:6px">
                  {{ task.duration_sec }}{{ t('common.seconds') }} · {{ task.elapsed_sec }}{{ t('common.seconds') }} · {{ task.created_at }}
                </div>
                <div v-if="task.status === 'failed'" style="color:#ef4444; font-size:11px; margin-top:6px">
                  {{ task.error }}
                </div>
              </n-card>
            </n-gi>
          </n-grid>
          <n-empty v-else :description="t('history.empty')" class="mt-16" />
        </n-card>
      </n-gi>
    </n-grid>
  </div>
</template>
