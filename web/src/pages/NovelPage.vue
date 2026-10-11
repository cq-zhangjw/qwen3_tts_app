<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { useI18n } from 'vue-i18n'
import {
  uploadNovel, listNovels, getNovel, dubNovel, redubNovelLine, editNovelLine,
  deleteNovelLine, assembleNovel, deleteNovel, getSystemInfo, listVoices, resplitNovel,
  addNovelCharacter
} from '../api'

const message = useMessage()
const { t, locale } = useI18n()

const projects = ref<any[]>([])
const current = ref<any>(null)
const uploading = ref(false)
const dubbing = ref(false)
const assembling = ref(false)
const splitting = ref(false)
const playingId = ref<string | null>(null)
const presetVoices = ref<any[]>([])
const customVoices = ref<any[]>([])
const voiceSearch = ref('')
const newCharName = ref('')
let timer: number | null = null

function localLabel(v: any) {
  return v[`label_${locale.value}`] || v.label_zh || v.name || v.id
}

const flatVoices = computed(() => {
  const all = [
    ...presetVoices.value.map((v: any) => ({ id: v.id, label: localLabel(v), group: 'preset' })),
    ...customVoices.value.filter((v: any) => v.status === 'ready')
      .map((v: any) => ({ id: v.id, label: `${v.name} [${t(`voiceType.${v.type}`)}]`, group: v.type }))
  ]
  const kw = voiceSearch.value.trim().toLowerCase()
  return kw ? all.filter(v => v.label.toLowerCase().includes(kw)) : all
})

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

async function onResplit() {
  if (!current.value) return
  splitting.value = true
  try {
    const res = await resplitNovel(current.value.id)
    current.value = res.data
    message.success(t('novel.resplit'))
  } finally {
    setTimeout(() => (splitting.value = false), 1000)
  }
}

async function onDub() {
  if (!current.value) return
  dubbing.value = true
  try { await dubNovel(current.value.id) } finally {
    setTimeout(() => (dubbing.value = false), 1500)
  }
}

async function onAssemble() {
  if (!current.value) return
  assembling.value = true
  try { await assembleNovel(current.value.id) } finally {
    setTimeout(() => (assembling.value = false), 1500)
  }
}

async function onAddCharacter() {
  if (!current.value || !newCharName.value.trim()) return
  try {
    const res = await addNovelCharacter(current.value.id, { name: newCharName.value.trim() })
    current.value.characters.push(res.data)
    newCharName.value = ''
  } catch (e: any) { message.error(e?.response?.data?.detail || 'Error') }
}

async function onRedub(line: any) {
  if (!current.value) return
  await redubNovelLine(current.value.id, line.id)
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

async function onDeleteProject(p: any) {
  await deleteNovel(p.id)
  if (current.value?.id === p.id) current.value = null
  await loadProjects()
}

function playLine(line: any) {
  if (!line.audio_url || playingId.value === line.id) return
  playingId.value = line.id
  const audio = new Audio(line.audio_url)
  audio.onended = () => (playingId.value = null)
  audio.play()
}

const doneCount = computed(() => current.value?.lines?.filter((l: any) => l.status === 'done').length || 0)
const totalCount = computed(() => current.value?.lines?.length || 0)
const statusType = (s: string) =>
  s === 'done' ? 'success' : s === 'failed' ? 'error' : (s === 'dubbing' || s === 'assembling' || s === 'running') ? 'info' : 'default'
const typeTag = (ty: string) =>
  ty === 'dialogue' ? 'success' : ty === 'sfx' ? 'warning' : 'default'

const historyColumns = [
  { title: '文件', key: 'filename' },
  { title: '状态', key: 'status' },
  { title: '进度', key: 'progress' },
  { title: '句数', key: 'count' },
  { title: '创建', key: 'created_at' },
  { title: '完成', key: 'completed_at' },
  { title: '操作', key: 'actions' },
]

onMounted(async () => {
  await loadVoices()
  await loadProjects()
  timer = window.setInterval(async () => {
    if (current.value && ['dubbing', 'assembling', 'ready', 'done'].includes(current.value.status)) {
      const res = await getNovel(current.value.id)
      current.value = res.data
    }
    await loadProjects()
  }, 2500)
})
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<template>
  <div class="page-wrap" style="max-width:1400px">
    <!-- Action bar (one row) -->
    <n-card bordered class="mb-16">
      <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap">
        <n-upload :show-file-list="false" @change="() => {}">
          <n-button type="primary" :loading="uploading" @click="() => document.getElementById('novel-file')?.click()">
            {{ t('novel.upload') }}
          </n-button>
        </n-upload>
        <input id="novel-file" type="file" accept=".txt" style="display:none" @change="onUpload" />
        <template v-if="current">
          <n-divider vertical />
          <n-button :loading="splitting" @click="onResplit">{{ t('novel.resplit') }}</n-button>
          <n-button type="info" :loading="dubbing" @click="onDub">{{ t('novel.dubAll') }}</n-button>
          <n-button :loading="assembling" @click="onAssemble">{{ t('novel.assemble') }}</n-button>
          <n-button v-if="current.final_audio_url" type="success" tag="a" :href="`/api/novel/projects/${current.id}/final`">
            {{ t('novel.download') }}
          </n-button>
          <n-divider vertical />
          <n-tag :type="statusType(current.status)">{{ current.status }}</n-tag>
          <n-progress style="width:160px" :percentage="totalCount ? Math.round(doneCount/totalCount*100) : 0" size="small" />
          <span style="color:#64748b; font-size:12px">{{ doneCount }}/{{ totalCount }}</span>
        </template>
      </div>
    </n-card>

    <n-empty v-if="!current" :description="t('novel.noProject')" class="mt-16" />

    <template v-else>
      <!-- Characters -->
      <n-card bordered class="mb-16" :title="t('novel.characters')">
        <div v-for="c in current.characters" :key="c.id"
          style="display:flex; align-items:center; gap:10px; padding:6px 0; flex-wrap:wrap">
          <n-tag :bordered="false" :color="{ color: c.color + '22', textColor: c.color, borderColor: c.color }">{{ c.name }}</n-tag>
          <n-select v-model:value="c.voice_id" :options="flatVoices" filterable style="width:220px" size="small" />
          <n-input v-model:value="c.instruct" :placeholder="t('studio.instructPlaceholder')" size="small" style="flex:1; min-width:160px" />
        </div>
        <div style="display:flex; gap:8px; margin-top:10px">
          <n-input v-model:value="newCharName" size="small" placeholder="手动追加角色名…" style="width:200px" @keyup.enter="onAddCharacter" />
          <n-button size="small" @click="onAddCharacter">{{ t('common.create') }}</n-button>
        </div>
      </n-card>

      <!-- Lines -->
      <n-card bordered class="mb-16" :title="`${t('novel.lines')} (${totalCount})`">
        <div v-for="line in current.lines" :key="line.id"
          style="display:flex; gap:10px; align-items:flex-start; padding:8px 0; border-bottom:1px solid #f1f5f9">
          <n-tag size="tiny" :type="typeTag(line.type)">{{ t(`novel.${line.type}`) }}</n-tag>
          <n-tag size="tiny" :type="statusType(line.status)">{{ line.status }}</n-tag>
          <div style="flex:1; min-width:0">
            <n-input v-model:value="line.text" type="textarea" :autosize="{ minRows: 1, maxRows: 4}" size="small" @blur="onEditLine(line)" />
            <div style="display:flex; gap:8px; margin-top:4px">
              <n-select v-model:value="line.character_id" size="tiny" style="width:120px"
                :options="current.characters.map((c: any) => ({ label: c.name, value: c.id }))" @update:value="onEditLine(line)" />
              <n-input v-model:value="line.instruct" size="tiny" style="width:180px" :placeholder="t('studio.instructPlaceholder')" @blur="onEditLine(line)" />
            </div>
          </div>
          <div style="display:flex; flex-direction:column; gap:4px">
            <n-button size="tiny" quaternary :disabled="!line.audio_url" @click="playLine(line)">
              {{ playingId === line.id ? '…' : t('common.play') }}
            </n-button>
            <n-button size="tiny" quaternary @click="onRedub(line)">{{ t('novel.redub') }}</n-button>
            <n-button size="tiny" quaternary type="error" @click="onDeleteLine(line)">{{ t('common.delete') }}</n-button>
          </div>
        </div>
      </n-card>

      <!-- History table at bottom -->
      <n-card bordered :title="t('history.title')">
        <n-data-table :columns="historyColumns" :data="projects" size="small" :pagination="{ pageSize: 8 }">
          <template #status="{ row }">
            <n-tag size="small" :type="statusType(row.status)">{{ row.status }}</n-tag>
          </template>
          <template #progress="{ row }">
            <n-progress size="small" :percentage="row.total_count ? Math.round((row.done_count||0)/row.total_count*100) : 0" />
          </template>
          <template #count="{ row }">{{ row.done_count||0 }}/{{ row.total_count||0 }}</template>
          <template #actions="{ row }">
            <n-button size="tiny" quaternary @click="selectProject(row.id)">{{ t('common.refresh') }}</n-button>
            <n-popconfirm @positive-click="onDeleteProject(row)">
              <template #trigger><n-button size="tiny" quaternary type="error">{{ t('common.delete') }}</n-button></template>
              {{ t('common.confirm') }}?
            </n-popconfirm>
          </template>
        </n-data-table>
      </n-card>
    </template>
  </div>
</template>
