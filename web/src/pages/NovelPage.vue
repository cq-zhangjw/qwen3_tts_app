<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { useI18n } from 'vue-i18n'
import {
  uploadNovel, listNovels, getNovel, dubNovel, redubNovelLine, editNovelLine,
  deleteNovelLine, assembleNovel, deleteNovel, getSystemInfo, listVoices,
  addNovelCharacter
} from '../api'

const message = useMessage()
const { t, locale } = useI18n()

const step = ref(0)
const projects = ref<any[]>([])
const current = ref<any>(null)
const uploading = ref(false)
const dubbing = ref(false)
const assembling = ref(false)
const playingId = ref<string | null>(null)
const presetVoices = ref<any[]>([])
const customVoices = ref<any[]>([])
const newCharName = ref('')
let timer: number | null = null

function localLabel(v: any) {
  return v[`label_${locale.value}`] || v.label_zh || v.name || v.id
}

const flatVoices = computed(() => [
  ...presetVoices.value.map((v: any) => ({ label: localLabel(v), value: v.id })),
  ...customVoices.value.filter((v: any) => v.status === 'ready')
    .map((v: any) => ({ label: `${v.name} [${t(`voiceType.${v.type}`)}]`, value: v.id }))
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
  projects.value = (await listNovels()).data || []
}
async function selectProject(id: string) {
  current.value = (await getNovel(id)).data
  step.value = 3
}

// custom-request: n-upload calls this with the chosen file
async function customUpload({ file, onFinish, onError }: any) {
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', file.file)
    const res = await uploadNovel(fd)
    current.value = res.data
    step.value = 1
    message.success(t('common.create'))
    await loadProjects()
    onFinish()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || 'Error')
    onError()
  } finally {
    uploading.value = false
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
  if (current.value?.id === p.id) { current.value = null; step.value = 0 }
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
  s === 'done' ? 'success' : s === 'failed' ? 'error' : (['dubbing','assembling','ready','running'].includes(s)) ? 'info' : 'default'
const typeTag = (ty: string) =>
  ty === 'dialogue' ? 'success' : ty === 'sfx' ? 'warning' : 'default'

const stepItems = [
  { title: t('novel.stepUpload') },
  { title: t('novel.stepCharacters') },
  { title: t('novel.stepLines') },
  { title: t('novel.stepDub') },
]

onMounted(async () => {
  await loadVoices()
  await loadProjects()
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
      <n-step v-for="(s, i) in stepItems" :key="i" :title="s.title" />
    </n-steps>

    <!-- Step 0: drag-drop upload -->
    <n-card v-if="step === 0" bordered>
      <n-upload :show-file-list="false" accept=".txt" :custom-request="customUpload">
        <n-upload-dragger style="padding:40px 20px">
          <div style="font-size:16px; font-weight:600">{{ t('novel.uploadHint') }}</div>
          <div style="color:#94a3b8; font-size:12px; margin-top:8px">{{ t('novel.upload') }}</div>
        </n-upload-dragger>
      </n-upload>
    </n-card>

    <template v-else-if="current">
      <!-- Step 1: characters -->
      <n-card v-if="step === 1" bordered class="mb-16" :title="t('novel.stepCharacters')">
        <div v-for="c in current.characters" :key="c.id"
          style="display:flex; align-items:center; gap:10px; padding:6px 0; flex-wrap:wrap">
          <n-tag :bordered="false" :color="{ color: c.color + '22', textColor: c.color, borderColor: c.color }">{{ c.name }}</n-tag>
          <n-select v-model:value="c.voice_id" :options="flatVoices" filterable size="small" style="width:220px" />
          <n-input v-model:value="c.instruct" :placeholder="t('studio.instructPlaceholder')" size="small" style="flex:1; min-width:160px" />
        </div>
        <div style="display:flex; gap:8px; margin-top:10px">
          <n-input v-model:value="newCharName" size="small" placeholder="手动追加角色名…" style="width:200px" @keyup.enter="onAddCharacter" />
          <n-button size="small" @click="onAddCharacter">{{ t('common.create') }}</n-button>
        </div>
        <div class="mt-16" style="display:flex; justify-content:flex-end; gap:8px">
          <n-button @click="step = 0">{{ t('common.cancel') }}</n-button>
          <n-button type="primary" @click="step = 2">{{ t('novel.next') }} →</n-button>
        </div>
      </n-card>

      <!-- Step 2: lines review -->
      <n-card v-if="step === 2" bordered class="mb-16" :title="`${t('novel.stepLines')} (${totalCount})`">
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
            <n-button size="tiny" quaternary :disabled="!line.audio_url" @click="playLine(line)">
              {{ playingId === line.id ? '…' : t('common.play') }}
            </n-button>
            <n-button size="tiny" quaternary @click="onRedub(line)">{{ t('novel.redub') }}</n-button>
            <n-button size="tiny" quaternary type="error" @click="onDeleteLine(line)">{{ t('common.delete') }}</n-button>
          </div>
        </div>
        <div class="mt-16" style="display:flex; justify-content:space-between; gap:8px">
          <n-button @click="step = 1">← {{ t('novel.prev') }}</n-button>
          <n-button type="primary" :loading="dubbing" @click="onDub">{{ t('novel.dubAll') }}</n-button>
        </div>
      </n-card>

      <!-- Step 3: dubbing progress + assemble -->
      <n-card v-if="step === 3" bordered class="mb-16">
        <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap">
          <n-tag :type="statusType(current.status)">{{ current.status }}</n-tag>
          <n-progress style="flex:1; min-width:200px" :percentage="totalCount ? Math.round(doneCount/totalCount*100) : 0" />
          <span style="color:#64748b; font-size:12px">{{ doneCount }}/{{ totalCount }}</span>
          <n-button size="small" :loading="dubbing" @click="onDub">{{ t('novel.dubAll') }}</n-button>
          <n-button size="small" :loading="assembling" @click="onAssemble">{{ t('novel.assemble') }}</n-button>
          <n-button v-if="current.final_audio_url" size="small" type="success" tag="a" :href="`/api/novel/projects/${current.id}/final`">
            {{ t('novel.download') }}
          </n-button>
        </div>
        <div v-for="line in current.lines" :key="line.id"
          style="display:flex; gap:10px; align-items:center; padding:6px 0; border-bottom:1px solid #f8fafc; font-size:12px">
          <n-tag size="tiny" :type="statusType(line.status)">{{ line.status }}</n-tag>
          <span style="flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:#475569">{{ line.text }}</span>
          <n-button size="tiny" quaternary :disabled="!line.audio_url" @click="playLine(line)">{{ t('common.play') }}</n-button>
          <n-button size="tiny" quaternary @click="onRedub(line)">{{ t('novel.redub') }}</n-button>
        </div>
      </n-card>
    </template>

    <!-- History table -->
    <n-card bordered :title="t('history.title')">
      <n-data-table :columns="[
        { title: '文件', key: 'filename' },
        { title: '状态', key: 'status' },
        { title: '进度', key: 'progress' },
        { title: '句数', key: 'count' },
        { title: '创建', key: 'created_at' },
        { title: '操作', key: 'actions' },
      ]" :data="projects" size="small" :pagination="{ pageSize: 8 }">
        <template #status="{ row }"><n-tag size="small" :type="statusType(row.status)">{{ row.status }}</n-tag></template>
        <template #progress="{ row }">
          <n-progress size="small" :percentage="row.total_count ? Math.round((row.done_count||0)/row.total_count*100) : 0" />
        </template>
        <template #count="{ row }">{{ row.done_count||0 }}/{{ row.total_count||0 }}</template>
        <template #actions="{ row }">
          <n-button size="tiny" quaternary @click="selectProject(row.id)">打开</n-button>
          <n-popconfirm @positive-click="onDeleteProject(row)">
            <template #trigger><n-button size="tiny" quaternary type="error">{{ t('common.delete') }}</n-button></template>
            {{ t('common.confirm') }}?
          </n-popconfirm>
        </template>
      </n-data-table>
    </n-card>
  </div>
</template>
