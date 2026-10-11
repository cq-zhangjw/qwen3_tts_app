<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { useI18n } from 'vue-i18n'
import {
  uploadNovel, listNovels, getNovel, dubNovel, redubNovelLine, editNovelLine,
  deleteNovelLine, assembleNovel, deleteNovel, getSystemInfo, listVoices, resplitNovel
} from '../api'

const message = useMessage()
const { t, locale } = useI18n()

const projects = ref<any[]>([])
const current = ref<any>(null)
const uploading = ref(false)
const dubbing = ref(false)
const assembling = ref(false)
const playingId = ref<string | null>(null)
const presetVoices = ref<any[]>([])
const customVoices = ref<any[]>([])
let timer: number | null = null

function localLabel(v: any) {
  return v[`label_${locale.value}`] || v.label_zh || v.name || v.id
}

const voiceOptions = computed(() => [
  {
    label: t('voices.filterPreset'),
    options: presetVoices.value.map(v => ({ label: localLabel(v), value: v.id }))
  },
  {
    label: t('voices.filterClone') + ' / ' + t('voices.filterDesign'),
    options: customVoices.value.filter((v: any) => v.status === 'ready')
      .map((v: any) => ({ label: `${v.name} [${t(`voiceType.${v.type}`)}]`, value: v.id }))
  }
])

async function loadVoices() {
  try {
    const sys = await getSystemInfo()
    presetVoices.value = sys.data.preset_voices || []
    const res = await listVoices()
    customVoices.value = res.data || []
  } catch { /* ignore */ }
}

async function loadProjects() {
  const res = await listNovels()
  projects.value = res.data || []
}

async function selectProject(id: string) {
  const res = await getNovel(id)
  current.value = res.data
}

async function onUpload(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const res = await uploadNovel(fd)
    message.success(t('common.create'))
    current.value = res.data
    await loadProjects()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || 'Error')
  } finally {
    uploading.value = false
    input.value = ''
  }
}

async function onDub() {
  if (!current.value) return
  dubbing.value = true
  try {
    await dubNovel(current.value.id)
    message.success(t('novel.dubbing'))
  } finally {
    setTimeout(() => (dubbing.value = false), 1500)
  }
}

async function onRedub(line: any) {
  if (!current.value) return
  await redubNovelLine(current.value.id, line.id)
  message.success(t('novel.redub'))
}

async function onEditLine(line: any) {
  await editNovelLine(current.value.id, line.id, {
    text: line.text, character_id: line.character_id, type: line.type, instruct: line.instruct
  })
}

async function onDeleteLine(line: any) {
  await deleteNovelLine(current.value.id, line.id)
  current.value.lines = current.value.lines.filter((l: any) => l.id !== line.id)
}

async function onAssemble() {
  if (!current.value) return
  assembling.value = true
  try {
    await assembleNovel(current.value.id)
    message.success(t('novel.assemble'))
  } finally {
    setTimeout(() => (assembling.value = false), 1500)
  }
}

async function onResplit() {
  if (!current.value) return
  const res = await resplitNovel(current.value.id)
  current.value = res.data
  message.success(t('novel.resplit'))
}

async function onDeleteProject() {
  if (!current.value) return
  await deleteNovel(current.value.id)
  current.value = null
  await loadProjects()
}

function playLine(line: any) {
  if (!line.audio_url) return
  if (playingId.value === line.id) return
  playingId.value = line.id
  const audio = new Audio(line.audio_url)
  audio.onended = () => (playingId.value = null)
  audio.play()
}

const doneCount = computed(() =>
  current.value?.lines?.filter((l: any) => l.status === 'done').length || 0)

const totalCount = computed(() => current.value?.lines?.length || 0)

const statusType = (s: string) =>
  s === 'done' ? 'success' : s === 'failed' ? 'error' : s === 'running' ? 'info' : 'default'

const typeTag = (ty: string) =>
  ty === 'dialogue' ? 'success' : ty === 'sfx' ? 'warning' : 'default'

onMounted(async () => {
  await loadVoices()
  await loadProjects()
  timer = window.setInterval(async () => {
    if (current.value && (current.value.status === 'dubbing' || current.value.status === 'assembling' || current.value.status === 'ready' || current.value.status === 'done')) {
      const res = await getNovel(current.value.id)
      current.value = res.data
    }
  }, 2000)
})

onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<template>
  <div class="page-wrap" style="max-width:1400px">
    <n-grid :cols="24" :responsive="['screen']" :x-gap="16" style="align-items:start">
      <!-- Left: project list / upload -->
      <n-gi :span="24" :span-laptop="6" :span-mobile="24">
        <n-card bordered class="mb-16">
          <n-upload :show-file-list="false" :custom-request="() => {}" @change="() => {}">
            <n-button type="primary" block :loading="uploading" @click="() => document.getElementById('novel-file')?.click()">
              {{ t('novel.upload') }}
            </n-button>
          </n-upload>
          <input id="novel-file" type="file" accept=".txt" style="display:none" @change="onUpload" />
          <div style="color:#94a3b8; font-size:11px; margin-top:8px">{{ t('novel.uploadHint') }}</div>
        </n-card>

        <n-card v-if="!projects.length" bordered>
          <n-empty :description="t('novel.noProject')" size="small" />
        </n-card>
        <n-card v-for="p in projects" :key="p.id" bordered class="mb-16"
          :style="{ cursor: 'pointer', borderColor: current?.id === p.id ? '#6366f1' : undefined }"
          @click="selectProject(p.id)">
          <div style="font-weight:600; font-size:13px">{{ p.filename }}</div>
          <div style="color:#64748b; font-size:11px; margin-top:4px">
            {{ p.done_count || 0 }}/{{ p.total_count || 0 }} · {{ p.status }}
          </div>
          <n-progress :percentage="p.total_count ? Math.round((p.done_count||0)/p.total_count*100) : 0"
            :show-indicator="false" height="4" class="mt-16" />
        </n-card>
      </n-gi>

      <!-- Right: workspace -->
      <n-gi :span="24" :span-laptop="18" :span-mobile="24">
        <n-empty v-if="!current" :description="t('novel.noProject')" class="mt-16" />
        <template v-else>
          <!-- action bar -->
          <n-card bordered class="mb-16">
            <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap">
              <div style="font-weight:700">{{ current.filename }}</div>
              <n-tag :type="statusType(current.status)">{{ current.status }}</n-tag>
              <n-button type="primary" :loading="dubbing" @click="onDub">{{ t('novel.dubAll') }}</n-button>
              <n-button :loading="assembling" @click="onAssemble">{{ t('novel.assemble') }}</n-button>
              <n-button @click="onResplit">{{ t('novel.resplit') }}</n-button>
              <n-button v-if="current.final_audio_url" type="success" tag="a"
                :href="`/api/novel/projects/${current.id}/final`">
                {{ t('novel.download') }}
              </n-button>
              <n-button type="error" ghost @click="onDeleteProject">{{ t('common.delete') }}</n-button>
            </div>
            <n-progress class="mt-16" :percentage="totalCount ? Math.round(doneCount/totalCount*100) : 0"
              :status="current.status === 'ready' || current.status === 'done' ? 'success' : 'info'" />
            <div style="color:#64748b; font-size:12px; margin-top:4px">{{ t('novel.progress') }}: {{ doneCount }}/{{ totalCount }}</div>
          </n-card>

          <!-- character voices -->
          <n-card bordered class="mb-16" :title="t('novel.characters')">
            <div v-for="c in current.characters" :key="c.id"
              style="display:flex; align-items:center; gap:10px; padding:6px 0; flex-wrap:wrap">
              <n-tag :bordered="false" :color="{ color: c.color + '22', textColor: c.color, borderColor: c.color }">
                {{ c.name }}
              </n-tag>
              <n-select v-model:value="c.voice_id" :options="voiceOptions" style="width:240px" filterable />
              <n-input v-model:value="c.instruct" :placeholder="t('studio.instructPlaceholder')" style="flex:1; min-width:180px" />
            </div>
          </n-card>

          <!-- lines -->
          <n-card bordered :title="`${t('novel.lines')} (${totalCount})`">
            <div v-for="line in current.lines" :key="line.id"
              style="display:flex; gap:10px; align-items:flex-start; padding:8px 0; border-bottom:1px solid #f1f5f9">
              <n-tag size="tiny" :type="typeTag(line.type)">{{ t(`novel.${line.type}`) }}</n-tag>
              <n-tag size="tiny" :type="statusType(line.status)">{{ line.status }}</n-tag>
              <div style="flex:1; min-width:0">
                <n-input v-model:value="line.text" type="textarea" :autosize="{ minRows: 1, maxRows: 4}"
                  size="small" @blur="onEditLine(line)" />
                <div style="display:flex; gap:8px; margin-top:4px; align-items:center">
                  <n-select v-model:value="line.character_id" size="tiny" style="width:130px"
                    :options="current.characters.map((c: any) => ({ label: c.name, value: c.id }))"
                    @update:value="onEditLine(line)" />
                  <n-input v-model:value="line.instruct" size="tiny" style="width:160px"
                    :placeholder="t('studio.instructPlaceholder')" @blur="onEditLine(line)" />
                </div>
              </div>
              <div style="display:flex; flex-direction:column; gap:4px">
                <n-button size="tiny" quaternary :disabled="!line.audio_url" @click="playLine(line)">
                  {{ playingId === line.id ? '…' : t('common.play') }}
                </n-button>
                <n-button size="tiny" quaternary @click="onRedub(line)">{{ t('novel.redub') }}</n-button>
                <n-button size="tiny" quaternary type="error" @click="onDeleteLine(line)">
                  {{ t('common.delete') }}
                </n-button>
              </div>
            </div>
          </n-card>
        </template>
      </n-gi>
    </n-grid>
  </div>
</template>
