<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, ref } from 'vue'
import { NTag, NButton, NProgress, NSelect, NInput, useMessage, NDropdown, NTooltip, NIcon } from 'naive-ui'
import { TrashOutline } from '@vicons/ionicons5'
import { useI18n } from 'vue-i18n'
import {
  uploadNovel, listNovels, getNovel, dubNovel, redubNovelLine, editNovelLine,
  deleteNovelLine, assembleNovel, deleteNovel, getSystemInfo, listVoices,
  addNovelCharacter, analyzeNovel, splitNovel, updateNovelCharacters
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
const playingProjectId = ref<string | null>(null)
const presetVoices = ref<any[]>([])
const customVoices = ref<any[]>([])
const newCharName = ref('')
const projects = ref<any[]>([])
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

function charName(p: any, cid: string) {
  const c = (p?.characters || []).find((x: any) => x.id === cid)
  return c?.name || '旁白'
}
function charGender(p: any, cid: string) {
  const c = (p?.characters || []).find((x: any) => x.id === cid)
  return c?.gender || '—'
}

async function openProject(id: string) {
  try {
    const res = await getNovel(id)
    current.value = res.data
    if (!current.value.characters?.length) step.value = 1
    else if (!current.value.lines?.length) step.value = 2
    else step.value = 3
  } catch (e: any) {
    message.error('打开失败: ' + (e?.response?.data?.detail || e?.message || e))
  }
}

function closeWizard() {
  current.value = null
  step.value = 0
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
    autoAssignVoices()
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

function removeCharacter(cid: string) {
  if (!current.value) return
  current.value.characters = current.value.characters.filter((c: any) => c.id !== cid)
}

function autoAssignVoices() {
  if (!current.value?.characters) return
  const zhPresets = presetVoices.value.filter((v: any) => v.language === 'zh')
  for (const c of current.value.characters) {
    if (!c.voice_id) {
      const gender = c.gender || 'male'
      const match = zhPresets.find((v: any) => v.gender === gender)
      c.voice_id = match?.id || zhPresets[0]?.id
    }
  }
}

async function saveCharacters() {
  if (!current.value) return
  try {
    const res = await updateNovelCharacters(current.value.id, current.value.characters)
    current.value.characters = res.data
  } catch (e: any) { message.error(e?.response?.data?.detail || '保存角色失败') }
}

async function onDub() {
  if (!current.value) return
  await saveCharacters()
  dubbing.value = true
  try {
    await dubNovel(current.value.id)
    message.success(t('novel.dubStarted') || '配音已开始')
    closeWizard()
    await loadProjects()
  } finally { setTimeout(() => dubbing.value = false, 1500) }
}
async function onAssemble(pid?: string) {
  const id = pid || current.value?.id
  if (!id) return
  assembling.value = true
  try { await assembleNovel(id); message.success(t('novel.assembling') || '合成中') }
  finally { setTimeout(() => assembling.value = false, 1500) }
}
async function onProjectDub(p: any) {
  await dubNovel(p.id)
  if (current.value?.id === p.id) await openProject(p.id)
  else await loadProjects()
}
async function onProjectPlay(p: any) {
  if (!p.final_audio_url) { message.warning(t('novel.noFinal') || '尚未合成完整音频'); return }
  playingProjectId.value = p.id
  const audio = new Audio(`/api/novel/projects/${p.id}/final`)
  audio.onended = () => playingProjectId.value = null
  audio.play()
}

async function onRedub(line: any) {
  await redubNovelLine(current.value!.id, line.id)
  message.success(t('novel.redubQueued') || '重配已加入队列')
}
async function onEditLine(line: any) {
  try {
    await editNovelLine(current.value!.id, line.id, {
      text: line.text, character_id: line.character_id, type: line.type, instruct: line.instruct
    })
  } catch (e: any) { message.error(e?.response?.data?.detail || 'Error') }
}
async function onEditLineFromProject(pid: string, line: any) {
  try {
    await editNovelLine(pid, line.id, {
      text: line.text, character_id: line.character_id, type: line.type, instruct: line.instruct
    })
    // refresh project
    const res = await getNovel(pid)
    const idx = projects.value.findIndex((x: any) => x.id === pid)
    if (idx >= 0) projects.value[idx] = res.data
  } catch (e: any) { message.error(e?.response?.data?.detail || 'Error') }
}
async function onDeleteLine(line: any) {
  await deleteNovelLine(current.value!.id, line.id)
  current.value.lines = current.value.lines.filter((l: any) => l.id !== line.id)
}
async function onDeleteLineFromProject(pid: string, line: any) {
  await deleteNovelLine(pid, line.id)
  const res = await getNovel(pid)
  const idx = projects.value.findIndex((x: any) => x.id === pid)
  if (idx >= 0) projects.value[idx] = res.data
}
async function onDeleteProject(p: any) {
  await deleteNovel(p.id)
  if (current.value?.id === p.id) closeWizard()
  await loadProjects()
}

function playLine(line: any) {
  if (!line.audio_url || playingId.value === line.id) return
  playingId.value = line.id
  const audio = new Audio(line.audio_url)
  audio.onended = () => playingId.value = null
  audio.play()
}
const playingLineId = ref<string | null>(null)
let currentAudio: HTMLAudioElement | null = null

function stopPlayback() {
  if (currentAudio) { currentAudio.pause(); currentAudio = null }
  playingLineId.value = null
}

function playLineFromProject(pid: string, line: any) {
  if (!line.audio_url) return
  // toggle: if playing this line, stop
  if (playingLineId.value === line.id) { stopPlayback(); return }
  stopPlayback()
  playingLineId.value = line.id
  currentAudio = new Audio(line.audio_url)
  currentAudio.onended = () => { playingLineId.value = null; currentAudio = null }
  currentAudio.play()
}

const doneCount = computed(() => current.value?.lines?.filter((l: any) => l.status === 'done').length || 0)
const totalCount = computed(() => current.value?.lines?.length || 0)
const statusType = (s: string) =>
  s === 'done' ? 'success' :
  s === 'error' ? 'error' :
  s === 'interrupt' ? 'warning' :
  s === 'running' || s === 'dubbing' ? 'info' :
  s === 'waiting' || s === 'ready' || s === 'characters' || s === 'uploaded' ? 'default' : 'default'
const typeTag = (ty: string) => ty === 'dialogue' ? 'success' : ty === 'sfx' ? 'warning' : 'default'

const stepItems = [
  t('novel.stepUpload'), t('novel.stepCharacters'), t('novel.stepLines'), t('novel.stepDub')
]

const downloadOptions = (pid: string) => [
  { label: t('novel.downloadMerged') || '合并下载 (final.wav)', key: 'merged', props: { style: 'font-size:12px' } },
  { label: t('novel.downloadSplit') || '分轨下载 (ZIP)', key: 'split', props: { style: 'font-size:12px' } },
]
function onDownloadSelect(key: string, pid: string) {
  if (key === 'merged') window.open(`/api/novel/projects/${pid}/final`, '_blank')
  else window.open(`/api/novel/projects/${pid}/zip`, '_blank')
}

function fmtTime(iso?: string) {
  if (!iso) return '—'
  return iso.replace('T', ' ').slice(0, 16)
}
function fmtDur(sec?: number) {
  if (!sec && sec !== 0) return '—'
  if (sec < 60) return `${sec}s`
  const m = Math.floor(sec / 60)
  const s = Math.round(sec % 60)
  return `${m}m${s}s`
}

function renderExpandRow(p: any) {
  const lines = p.lines || []
  const charOptions = (p.characters || []).map((c: any) => ({ label: c.name, value: c.id }))
  const iconBtn = (icon: string, tip: string, onClick: () => void, disabled = false, color = '#6366f1') =>
    h(NTooltip, { trigger: 'hover' }, {
      trigger: () => h('button', {
        style: `font-size:13px;width:24px;height:24px;border-radius:4px;border:1px solid #e2e8f0;background:#fff;cursor:${disabled ? 'not-allowed' : 'pointer'};color:${disabled ? '#cbd5e1' : color};display:inline-flex;align-items:center;justify-content:center;`,
        disabled, onClick,
      }, icon),
      default: () => tip,
    })
  return h('div', { style: 'padding:8px 16px;background:#f8fafc;border-radius:8px;max-height:300px;overflow-y:auto' }, [
    ...lines.map((l: any) => {
      const cgender = charGender(p, l.character_id)
      const isPlaying = playingLineId.value === l.id
      return h('div', { key: l.id, style: 'padding:8px 0;border-bottom:1px solid #e2e8f0' }, [
        h('div', { style: 'display:flex;gap:8px;align-items:flex-start;font-size:12px' }, [
          h(NTag, { size: 'tiny', type: statusType(l.status), style: 'flex-shrink:0;margin-top:3px' }, { default: () => l.status }),
          h('div', { style: 'flex:1;min-width:0' }, [
            h(NInput, {
              value: l.text, type: 'textarea', autosize: { minRows: 1, maxRows: 4 }, size: 'small',
              onBlur: () => onEditLineFromProject(p.id, l),
              'onUpdate:value': (v: string) => { l.text = v },
            }),
          ]),
          h('div', { style: 'display:flex;gap:4px;flex-shrink:0' }, [
            iconBtn(isPlaying ? '⏸' : '▶', isPlaying ? '停止' : '播放', () => playLineFromProject(p.id, l), !l.audio_url, '#6366f1'),
            iconBtn('⬇', '下载', () => { const a = document.createElement('a'); a.href = `/api/novel/projects/${p.id}/lines/${l.id}/audio`; a.download = `line_${l.id}.wav`; a.click() }, !l.audio_url, '#475569'),
            iconBtn('↻', '重配', () => redubFromProject(p.id, l), false, '#f59e0b'),
            iconBtn('✕', '删除', () => onDeleteLineFromProject(p.id, l), false, '#ef4444'),
          ]),
        ]),
        h('div', { style: 'display:flex;gap:10px;margin-top:4px;margin-left:56px;flex-wrap:wrap;align-items:center;font-size:11px;color:#94a3b8' }, [
          h(NSelect, {
            value: l.character_id, size: 'tiny', style: 'width:100px', options: charOptions,
            onUpdateValue: (v: string) => { l.character_id = v; onEditLineFromProject(p.id, l) },
          }),
          h('span', null, `(${cgender})`),
          h('span', null, `⏱ ${fmtTime(l.started_at)} → ${fmtTime(l.finished_at)}`),
          h('span', null, `耗时 ${fmtDur(l.elapsed_sec)}`),
          h(NInput, {
            value: l.instruct, size: 'tiny', style: 'width:200px', placeholder: '提示词，如"用激昂的语气说"',
            onBlur: () => onEditLineFromProject(p.id, l),
            'onUpdate:value': (v: string) => { l.instruct = v },
          }),
        ]),
      ])
    }),
  ])
}

const expandedPid = ref<string | null>(null)
const expandedProject = computed(() => projects.value.find((p: any) => p.id === expandedPid.value) || null)

async function redubFromProject(pid: string, line: any) {
  await redubNovelLine(pid, line.id)
  message.success(t('novel.redubQueued') || '重配已加入队列')
  const res = await getNovel(pid)
  const idx = projects.value.findIndex((x: any) => x.id === pid)
  if (idx >= 0) projects.value[idx] = res.data
}

function toggleExpand(pid: string) {
  expandedPid.value = expandedPid.value === pid ? null : pid
}

const tableColumns = computed(() => [
  {
    type: 'expand',
    expandable: (r: any) => (r.lines?.length || 0) > 0,
    renderExpand: (r: any) => renderExpandRow(r),
  },
  { title: '文件', key: 'filename', width: 160, ellipsis: { tooltip: true } },
  {
    title: '状态', key: 'status', width: 90,
    render: (r: any) => h(NTag, { size: 'small', type: statusType(r.status) }, { default: () => r.status }),
  },
  {
    title: '进度', key: 'progress', width: 130,
    render: (r: any) => h('div', { style: 'display:flex;align-items:center;gap:6px' }, [
      `${r.done_count || 0}/${r.total_count || 0}`,
      h(NProgress, { size: 'small', percentage: r.total_count ? Math.round((r.done_count || 0) / r.total_count * 100) : 0, showIndicator: false, style: 'width:60px' }),
    ]),
  },
  { title: '创建', key: 'created_at', width: 130, render: (r: any) => h('span', { style: 'font-size:12px;color:#94a3b8' }, fmtTime(r.created_at)) },
  { title: '终了时间', key: 'ended_at', width: 130, render: (r: any) => h('span', { style: 'font-size:12px;color:#94a3b8' }, fmtTime(r.ended_at)) },
  { title: '耗时', key: 'elapsed_sec', width: 80, render: (r: any) => h('span', { style: 'font-size:12px;color:#94a3b8' }, fmtDur(r.elapsed_sec)) },
  {
    title: '操作', key: 'actions', width: 220,
    render: (r: any) => {
      const obtn = (icon: string, tip: string, onClick: () => void, disabled = false, color = '#6366f1') =>
        h(NTooltip, { trigger: 'hover' }, {
          trigger: () => h('button', {
            style: `font-size:13px;width:26px;height:26px;border-radius:6px;border:1px solid #e2e8f0;background:#fff;cursor:${disabled ? 'not-allowed' : 'pointer'};color:${disabled ? '#cbd5e1' : color};display:inline-flex;align-items:center;justify-content:center;`,
            disabled, onClick,
          }, icon),
          default: () => tip,
        })
      return h('div', { style: 'display:flex;gap:4px;flex-wrap:wrap' }, [
        obtn('📂', '打开', () => openProject(r.id), false, '#6366f1'),
        obtn('🎙', '开始配音', () => onProjectDub(r), false, '#6366f1'),
        obtn('🎵', '合成音频', () => onAssemble(r.id), false, '#8b5cf6'),
        obtn(playingProjectId.value === r.id ? '⏸' : '▶', playingProjectId.value === r.id ? '停止' : '播放', () => onProjectPlay(r), !r.final_audio_url, '#22c55e'),
        h(NDropdown, {
          options: downloadOptions(r.id), trigger: 'click',
          onSelect: (key: string) => onDownloadSelect(key, r.id),
        }, {
          trigger: () => obtn('⬇', '下载（合并/分轨）', () => {}, !r.final_audio_url, '#475569'),
        }),
        obtn('✕', '删除项目', () => onDeleteProject(r), false, '#ef4444'),
      ])
    },
  },
])

onMounted(async () => {
  await loadVoices(); await loadProjects()
  timer = window.setInterval(async () => {
    if (current.value && ['dubbing','assembling'].includes(current.value.status)) {
      current.value = (await getNovel(current.value.id)).data
    }
    // only refresh list when there's actually an active dubbing/assembling task
    const active = projects.value.filter((p: any) => ['dubbing','assembling'].includes(p.status))
    if (active.length > 0) {
      await loadProjects()
    }
  }, 2500)
})
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<template>
  <div class="page-wrap" style="max-width:1100px">
    <!-- Step bar -->
    <n-steps :current="step" size="small" class="mb-16" :number-style="{ fontWeight: 700 }">
      <n-step v-for="(s, i) in stepItems" :key="i" :title="s" />
    </n-steps>

    <!-- Step 0: upload -->
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
      <!-- Step 1: characters -->
      <n-card v-if="step === 1" bordered class="mb-16">
        <template #header>{{ t('novel.stepCharacters') }}</template>
        <div style="background:#f8fafc; padding:12px; border-radius:8px; max-height:200px; overflow:auto; font-size:13px; color:#475569">
          {{ current.raw_text }}
        </div>
        <div class="mt-16" v-if="!current.characters?.length">
          <n-button type="primary" :loading="analyzing" @click="onAnalyze">🤖 {{ t('novel.analyzeBtn') }}</n-button>
        </div>
        <div v-else class="mt-16">
          <div v-for="c in current.characters" :key="c.id"
            style="display:flex; align-items:center; gap:8px; padding:6px 0; flex-wrap:wrap">
            <n-input v-model:value="c.name" size="small" style="width:100px" />
            <n-select v-model:value="c.gender" size="small" style="width:70px"
              :options="[{label:'男',value:'male'},{label:'女',value:'female'},{label:'?',value:'unknown'}]" />
            <n-select v-model:value="c.voice_id" :options="flatVoices" filterable size="small" style="width:240px" />
            <n-button size="tiny" type="error" ghost @click="removeCharacter(c.id)">
              <template #icon><n-icon><TrashOutline /></n-icon></template>
            </n-button>
          </div>
          <div style="display:flex; gap:8px; margin-top:10px">
            <n-input v-model:value="newCharName" size="small" placeholder="手动追加角色名…" style="width:200px" @keyup.enter="onAddCharacter" />
            <n-button size="small" @click="onAddCharacter">{{ t('common.create') }}</n-button>
          </div>
        </div>
        <!-- bottom nav -->
        <div class="mt-16" style="display:flex; justify-content:space-between">
          <n-button @click="closeWizard">← {{ t('novel.prev') || '上一步' }}</n-button>
          <n-button type="primary" :disabled="!current.characters?.length" @click="saveCharacters().then(() => step = 2)">{{ t('novel.next') || '下一步' }} →</n-button>
        </div>
      </n-card>

      <!-- Step 2: lines review -->
      <n-card v-if="step === 2" bordered class="mb-16">
        <template #header>{{ t('novel.stepLines') }} ({{ totalCount }})</template>
        <div v-if="!current.lines?.length">
          <n-button type="primary" :loading="splitting" @click="onSplit">✂️ {{ t('novel.splitBtn') }}</n-button>
        </div>
        <div v-else class="mt-8">
          <div v-for="line in current.lines" :key="line.id"
            style="display:flex; gap:10px; align-items:flex-start; padding:8px 0; border-bottom:1px solid #f1f5f9">
            <n-tag size="tiny" :type="typeTag(line.type)">{{ t(`novel.${line.type}`) }}</n-tag>
            <n-tag size="tiny" :type="statusType(line.status)">{{ line.status }}</n-tag>
            <div style="flex:1; min-width:0">
              <n-input v-model:value="line.text" type="textarea" :autosize="{ minRows:1, maxRows:4 }" size="small" @blur="onEditLine(line)" />
              <div style="display:flex; gap:8px; margin-top:4px">
                <n-select v-model:value="line.character_id" size="tiny" style="width:120px"
                  :options="current.characters.map((c:any)=>({label:c.name, value:c.id}))" @update:value="onEditLine(line)" />
                <n-input v-model:value="line.instruct" size="tiny" style="width:200px" :placeholder="t('studio.instructPlaceholder')" @blur="onEditLine(line)" />
              </div>
            </div>
            <div style="display:flex; flex-direction:column; gap:4px">
              <n-button size="tiny" quaternary :disabled="!line.audio_url" @click="playLine(line)">{{ playingId===line.id?'…':t('common.play') }}</n-button>
              <n-button size="tiny" quaternary @click="onRedub(line)">{{ t('novel.redub') }}</n-button>
              <n-button size="tiny" quaternary type="error" @click="onDeleteLine(line)">{{ t('common.delete') }}</n-button>
            </div>
          </div>
        </div>
        <div class="mt-16" style="display:flex; justify-content:space-between">
          <n-button @click="step = 1">← {{ t('novel.prev') || '上一步' }}</n-button>
          <n-button type="primary" :disabled="!current.lines?.length" @click="step = 3">{{ t('novel.next') || '下一步' }} →</n-button>
        </div>
      </n-card>

      <!-- Step 3: dub -->
      <n-card v-if="step === 3" bordered class="mb-16">
        <template #header>{{ t('novel.stepDub') }}</template>
        <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap; padding:16px 0">
          <n-tag :type="statusType(current.status)">{{ current.status }}</n-tag>
          <n-progress style="flex:1; min-width:200px" :percentage="totalCount ? Math.round(doneCount/totalCount*100) : 0" />
          <span style="color:#64748b; font-size:13px">{{ doneCount }}/{{ totalCount }}</span>
        </div>
        <div v-if="current.final_audio_url" class="mt-8">
          <n-alert type="success" :show-icon="true">{{ t('novel.assembled') || '合成完成，可在下方履历表下载' }}</n-alert>
        </div>
        <div class="mt-16" style="display:flex; justify-content:space-between">
          <n-button @click="step = 2">← {{ t('novel.prev') || '上一步' }}</n-button>
          <n-button type="primary" size="large" :loading="dubbing" @click="onDub">▶️ {{ t('novel.dubAll') }}</n-button>
        </div>
      </n-card>
    </template>

    <!-- History table -->
    <n-card bordered :title="t('history.title')">
      <n-data-table :columns="tableColumns" :data="projects" :row-key="(r:any)=>r.id" size="small" :pagination="{ pageSize: 8 }" expand-trigger="row" />
    </n-card>
  </div>
</template>
