<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, ref } from 'vue'
import { NProgress, NTag, NButton, useMessage } from 'naive-ui'
import { useI18n } from 'vue-i18n'
import {
  uploadNovel, listNovels, getNovel, dubNovel, redubNovelLine, editNovelLine,
  deleteNovelLine, assembleNovel, deleteNovel, getSystemInfo, listVoices,
  addNovelCharacter, analyzeNovel, splitNovel
} from '../api'

const message = useMessage()
const { t, locale } = useI18n()

const step = ref(0)
const current = ref<any>(null)
const uploading = ref(false)
const analyzing = ref(false)
const splitting = ref(false)
const dubbing = ref(false)
const assembling = ref(false)
const playingId = ref<string | null>(null)
const presetVoices = ref<any[]>([])
const customVoices = ref<any[]>([])
const newCharName = ref('')
const expandedRow = ref<string | null>(null)
let timer: number | null = null

function localLabel(v: any) {
  return v[`label_${locale.value}`] || v.label_zh || v.name || v.id
}
function langTag(l?: string) {
  return l === 'ja' ? '日本語' : l === 'en' ? 'EN' : '中文'
}

const flatVoices = computed(() => [
  ...presetVoices.value.map((v: any) => ({ label: `${localLabel(v)} · ${langTag(v.language)}`, value: v.id })),
  ...customVoices.value.filter((v: any) => v.status === 'ready')
    .map((v: any) => ({ label: `${v.name} [${t(`voiceType.${v.type}`)}·${langTag(v.language)}]`, value: v.id }))
])

async function loadVoices() {
  try {
    const sys = await getSystemInfo()
    presetVoices.value = sys.data.preset_voices || []
    customVoices.value = (await listVoices()).data || []
  } catch { /* ignore */ }
}
async function loadProjects() {
  projects.value = (await listNovels()).data || []
}
const projects = ref<any[]>([])

async function openProject(id: string) {
  current.value = (await getNovel(id)).data
  // jump to the latest meaningful step
  if (!current.value.characters?.length) step.value = 1
  else if (!current.value.lines?.length) step.value = 2
  else step.value = 3
}

async function customUpload({ file, onFinish, onError }: any) {
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', file.file)
    current.value = (await uploadNovel(fd)).data
    step.value = 1
    message.success(t('common.create'))
    await loadProjects()
    onFinish()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || 'Error'); onError()
  } finally { uploading.value = false }
}

async function onAnalyze() {
  analyzing.value = true
  try {
    current.value = (await analyzeNovel(current.value.id)).data
    message.success(t('novel.stepCharacters'))
  } finally { setTimeout(() => analyzing.value = false, 800) }
}
async function onSplit() {
  splitting.value = true
  try {
    current.value = (await splitNovel(current.value.id)).data
    message.success(t('novel.stepLines'))
  } finally { setTimeout(() => splitting.value = false, 800) }
}
async function onAddCharacter() {
  if (!current.value || !newCharName.value.trim()) return
  try {
    const res = await addNovelCharacter(current.value.id, { name: newCharName.value.trim() })
    current.value.characters.push(res.data); newCharName.value = ''
  } catch (e: any) { message.error(e?.response?.data?.detail || 'Error') }
}
async function onDub() {
  if (!current.value) return
  dubbing.value = true
  try { await dubNovel(current.value.id) } finally { setTimeout(() => dubbing.value = false, 1500) }
}
async function onAssemble() {
  if (!current.value) return
  assembling.value = true
  try { await assembleNovel(current.value.id) } finally { setTimeout(() => assembling.value = false, 1500) }
}
async function onRedub(line: any) { await redubNovelLine(current.value.id, line.id) }
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
  if (current.value?.id === p.id) { current.value = null; step.value = 0 }
  await loadProjects()
}
async function onProjectDub(p: any) { await dubNovel(p.id); if (current.value?.id === p.id) await openProject(p.id) }
async function onProjectAssemble(p: any) { await assembleNovel(p.id) }

function playLine(line: any) {
  if (!line.audio_url || playingId.value === line.id) return
  playingId.value = line.id
  const audio = new Audio(line.audio_url)
  audio.onended = () => playingId.value = null
  audio.play()
}

const doneCount = computed(() => current.value?.lines?.filter((l: any) => l.status === 'done').length || 0)
const totalCount = computed(() => current.value?.lines?.length || 0)
const statusType = (s: string) =>
  s === 'done' ? 'success' : s === 'failed' ? 'error' : (['dubbing','assembling','ready','running','characters','uploaded'].includes(s)) ? 'info' : 'default'
const typeTag = (ty: string) => ty === 'dialogue' ? 'success' : ty === 'sfx' ? 'warning' : 'default'

const stepItems = [
  t('novel.stepUpload'), t('novel.stepCharacters'), t('novel.stepLines'), t('novel.stepDub')
]

const tableColumns = computed(() => [
  { type: 'expand', expandable: (r: any) => r.lines?.length > 0, renderExpand: (r: any) => h('div', { style: 'padding:8px 16px;background:#f8fafc;border-radius:6px' },
    (r.lines || []).map((l: any) => h('div', { style: 'display:flex;gap:8px;padding:3px 0;font-size:12px;align-items:center' }, [
      h(NTag, { size: 'tiny', type: statusType(l.status) }, () => l.status),
      h('span', { style: 'flex:1;color:#475569;overflow:hidden;text-overflow:ellipsis;white-space:nowrap' }, l.text),
    ])))
  },
  { title: '文件', key: 'filename' },
  { title: '状态', key: 'status', render: (r: any) => h(NTag, { size: 'small', type: statusType(r.status) }, () => r.status) },
  { title: '进度', key: 'progress', render: (r: any) => h('div', { style: 'display:flex;align-items:center;gap:6px' }, [
    `${r.done_count || 0}/${r.total_count || 0}`,
    h(NProgress, { size: 'small', percentage: r.total_count ? Math.round((r.done_count || 0) / r.total_count * 100) : 0, showIndicator: false, style: 'width:80px' })
  ]) },
  { title: '创建', key: 'created_at', render: (r: any) => h('span', { style: 'font-size:12px;color:#94a3b8' }, (r.created_at || '').replace('T', ' ').slice(0, 16)) },
  { title: '操作', key: 'actions', render: (r: any) => h('div', { style: 'display:flex;gap:4px' }, [
    h('button', { style: 'font-size:12px;padding:2px 10px;border:1px solid #e2e8f0;border-radius:6px;background:#fff;color:#6366f1;cursor:pointer', onClick: () => openProject(r.id) }, '打开'),
    h('button', { style: 'font-size:12px;padding:2px 10px;border:1px solid #e2e8f0;border-radius:6px;background:#fff;color:#475569;cursor:pointer', onClick: () => onProjectDub(r) }, '配音'),
    h('button', { style: 'font-size:12px;padding:2px 10px;border:1px solid #e2e8f0;border-radius:6px;background:#fff;color:#475569;cursor:pointer', onClick: () => onProjectAssemble(r) }, '合成'),
    r.final_audio_url
      ? h('a', { style: 'font-size:12px;padding:2px 10px;border:1px solid #bbf7d0;border-radius:6px;background:#f0fdf4;color:#16a34a;cursor:pointer;text-decoration:none', href: `/api/novel/projects/${r.id}/final` }, '下载')
      : h('span', { style: 'font-size:12px;padding:2px 10px;color:#cbd5e1' }, '下载'),
  ]) },
])

onMounted(async () => {
  await loadVoices(); await loadProjects()
  timer = window.setInterval(async () => {
    if (current.value && ['dubbing','assembling','ready','done'].includes(current.value.status)) {
      current.value = (await getNovel(current.value.id)).data
    }
    await loadProjects()
  }, 2500)
})
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<template>
  <div class="page-wrap" style="max-width:1100px">
    <n-steps :current="step" size="small" class="mb-16" :number-style="{ fontWeight: 700 }">
      <n-step v-for="(s, i) in stepItems" :key="i" :title="s" />
    </n-steps>

    <!-- Step 0: square drag upload -->
    <n-card v-if="step === 0" bordered>
      <n-upload :show-file-list="false" accept=".txt" :custom-request="customUpload">
        <n-upload-dragger style="width:320px; height:240px; margin:0 auto; display:flex; align-items:center; justify-content:center">
          <div style="text-align:center">
            <div style="font-size:36px; color:#6366f1; margin-bottom:10px">📄</div>
            <n-button type="primary" :loading="uploading">{{ t('novel.upload') }}</n-button>
            <div style="color:#94a3b8; font-size:12px; margin-top:10px">{{ t('novel.uploadHint') }}</div>
          </div>
        </n-upload-dragger>
      </n-upload>
    </n-card>

    <template v-else-if="current">
      <!-- Step 1: raw text preview + analyze characters -->
      <n-card v-if="step === 1" bordered class="mb-16">
        <template #header>{{ t('novel.stepCharacters') }}</template>
        <div style="background:#f8fafc; padding:12px; border-radius:8px; max-height:200px; overflow:auto; font-size:13px; color:#475569">
          {{ current.raw_text }}
        </div>
        <div class="mt-16" style="display:flex; justify-content:space-between">
          <n-button @click="step = 0">{{ t('novel.prev') }}</n-button>
          <n-button type="primary" :loading="analyzing" @click="onAnalyze">🤖 {{ t('novel.analyzeBtn') }}</n-button>
        </div>
        <div v-if="current.characters?.length" class="mt-16">
          <div v-for="c in current.characters" :key="c.id" style="padding:4px 0">
            <n-tag :bordered="false" :color="{ color: c.color + '22', textColor: c.color, borderColor: c.color }">{{ c.name }}</n-tag>
          </div>
          <n-button type="primary" class="mt-16" @click="step = 2">{{ t('novel.next') }} →</n-button>
        </div>
      </n-card>

      <!-- Step 2: assign voices + split -->
      <n-card v-if="step === 2" bordered class="mb-16">
        <template #header>{{ t('novel.stepCharacters') }} · {{ t('novel.voices') }}</template>
        <div v-for="c in current.characters" :key="c.id"
          style="display:flex; align-items:center; gap:10px; padding:6px 0; flex-wrap:wrap">
          <n-tag :bordered="false" :color="{ color: c.color + '22', textColor: c.color, borderColor: c.color }">{{ c.name }}</n-tag>
          <n-select v-model:value="c.voice_id" :options="flatVoices" filterable size="small" style="width:260px" />
          <n-input v-model:value="c.instruct" :placeholder="t('studio.instructPlaceholder')" size="small" style="flex:1; min-width:160px" />
        </div>
        <div style="display:flex; gap:8px; margin-top:10px">
          <n-input v-model:value="newCharName" size="small" placeholder="手动追加角色名…" style="width:200px" @keyup.enter="onAddCharacter" />
          <n-button size="small" @click="onAddCharacter">{{ t('common.create') }}</n-button>
        </div>
        <div class="mt-16" style="display:flex; justify-content:space-between">
          <n-button @click="step = 1">{{ t('novel.prev') }}</n-button>
          <n-button type="primary" :loading="splitting" @click="onSplit">✂️ {{ t('novel.splitBtn') }}</n-button>
        </div>
        <div v-if="current.lines?.length" class="mt-16">
          <n-button type="primary" @click="step = 3">{{ t('novel.next') }} →</n-button>
        </div>
      </n-card>

      <!-- Step 3: lines review + dub -->
      <n-card v-if="step === 3" bordered class="mb-16">
        <template #header>{{ t('novel.stepLines') }} ({{ totalCount }})</template>
        <div v-for="line in current.lines" :key="line.id"
          style="display:flex; gap:10px; align-items:flex-start; padding:8px 0; border-bottom:1px solid #f1f5f9">
          <n-tag size="tiny" :type="typeTag(line.type)">{{ t(`novel.${line.type}`) }}</n-tag>
          <n-tag size="tiny" :type="statusType(line.status)">{{ line.status }}</n-tag>
          <div style="flex:1; min-width:0">
            <n-input v-model:value="line.text" type="textarea" :autosize="{ minRows:1, maxRows:4 }" size="small" @blur="onEditLine(line)" />
            <div style="display:flex; gap:8px; margin-top:4px">
              <n-select v-model:value="line.character_id" size="tiny" style="width:120px"
                :options="current.characters.map((c:any)=>({label:c.name, value:c.id}))" @update:value="onEditLine(line)" />
              <n-input v-model:value="line.instruct" size="tiny" style="width:180px" :placeholder="t('studio.instructPlaceholder')" @blur="onEditLine(line)" />
            </div>
          </div>
          <div style="display:flex; flex-direction:column; gap:4px">
            <n-button size="tiny" quaternary :disabled="!line.audio_url" @click="playLine(line)">{{ playingId===line.id?'…':t('common.play') }}</n-button>
            <n-button size="tiny" quaternary @click="onRedub(line)">{{ t('novel.redub') }}</n-button>
            <n-button size="tiny" quaternary type="error" @click="onDeleteLine(line)">{{ t('common.delete') }}</n-button>
          </div>
        </div>
        <div class="mt-16" style="display:flex; justify-content:space-between; align-items:center">
          <n-button @click="step = 2">{{ t('novel.prev') }}</n-button>
          <n-button type="primary" :loading="dubbing" @click="onDub">▶️ {{ t('novel.dubAll') }}</n-button>
        </div>
      </n-card>

      <!-- Step 4: progress -->
      <n-card v-if="step === 4 || (step === 3 && current.status !== 'ready')" bordered class="mb-16">
        <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap">
          <n-tag :type="statusType(current.status)">{{ current.status }}</n-tag>
          <n-progress style="flex:1; min-width:200px" :percentage="totalCount ? Math.round(doneCount/totalCount*100) : 0" />
          <span style="color:#64748b; font-size:12px">{{ doneCount }}/{{ totalCount }}</span>
          <n-button size="small" :loading="dubbing" @click="onDub">{{ t('novel.dubAll') }}</n-button>
          <n-button size="small" :loading="assembling" @click="onAssemble">{{ t('novel.assemble') }}</n-button>
          <n-button v-if="current.final_audio_url" size="small" type="success" tag="a" :href="`/api/novel/projects/${current.id}/final`">{{ t('novel.download') }}</n-button>
        </div>
      </n-card>
    </template>

    <!-- History table with expandable rows -->
    <n-card bordered :title="t('history.title')">
      <n-data-table :columns="tableColumns" :data="projects" size="small" :pagination="{ pageSize: 8 }" />
    </n-card>
  </div>
</template>
