<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { useI18n } from 'vue-i18n'
import { createTask, getSystemInfo, listVoices, getTask } from '../api'

const message = useMessage()
const { t } = useI18n()

const text = ref('')
const voiceId = ref('')
const language = ref('auto')
const instruct = ref('')
const submitting = ref(false)

const presetVoices = ref<any[]>([])
const customVoices = ref<any[]>([])

const voiceOptions = computed(() => [
  {
    label: t('voices.filterPreset'),
    options: presetVoices.value.map(v => ({ label: `${v.label} (${v.speaker})`, value: v.id }))
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

const currentTask = ref<any>(null)
const polling = ref<number | null>(null)

onMounted(async () => {
  try {
    const sys = await getSystemInfo()
    presetVoices.value = sys.data.preset_voices || []
  } catch (e) { /* ignore */ }
  await loadCustom()
  if (presetVoices.value.length) voiceId.value = presetVoices.value[0].id
})

async function loadCustom() {
  try {
    const res = await listVoices()
    customVoices.value = res.data || []
  } catch (e) { /* ignore */ }
}

async function onSubmit() {
  if (!text.value.trim()) { message.warning(t('studio.needText')); return }
  if (!voiceId.value) { message.warning(t('studio.needVoice')); return }
  submitting.value = true
  currentTask.value = null
  try {
    const res = await createTask({
      text: text.value,
      voice_id: voiceId.value,
      language: language.value,
      instruct: instruct.value || null
    })
    message.success(t('studio.submitted'))
    await pollTask(res.data.id)
  } catch (e: any) {
    message.error(e?.response?.data?.detail || 'Error')
  } finally {
    submitting.value = false
  }
}

async function pollTask(id: string) {
  if (polling.value) window.clearTimeout(polling.value)
  const tick = async () => {
    try {
      const res = await getTask(id)
      currentTask.value = res.data
      if (res.data.status === 'completed' || res.data.status === 'failed') return
      polling.value = window.setTimeout(tick, 1500)
    } catch (e) { /* ignore */ }
  }
  await tick()
}

const audioSrc = computed(() => currentTask.value?.audio_url || '')
</script>

<template>
  <div class="page-wrap">
    <n-grid :cols="24" :responsive="['screen']" :x-gap="16">
      <n-gi :span="24" :span-tablet="12" :span-mobile="24">
        <n-card bordered class="mb-16" :title="t('studio.title')">
          <n-input
            v-model:value="text"
            type="textarea"
            :rows="9"
            :placeholder="t('studio.textPlaceholder')"
            show-count
          />
          <div class="mt-16 flex gap-16" style="flex-wrap:wrap">
            <n-select v-model:value="voiceId" :options="voiceOptions" style="min-width:220px" style-flex="1" />
            <n-select v-model:value="language" :options="langOptions" style="width:150px" />
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

      <n-gi :span="24" :span-tablet="12" :span-mobile="24">
        <n-card bordered :title="t('studio.result')">
          <n-spin :show="currentTask && (currentTask.status === 'pending' || currentTask.status === 'running')">
            <div v-if="currentTask && currentTask.status === 'completed'">
              <audio v-if="audioSrc" :src="audioSrc" controls class="audio-player" />
              <div class="mt-16 flex gap-8">
                <n-button size="small" tag="a" :href="audioSrc" download>
                  {{ t('common.download') }}
                </n-button>
                <n-tag size="small" type="success">{{ t('status.completed') }}</n-tag>
                <n-tag size="small">{{ t('history.duration') }}: {{ currentTask.duration_sec }}{{ t('common.seconds') }}</n-tag>
                <n-tag size="small">{{ t('history.elapsed') }}: {{ currentTask.elapsed_sec }}{{ t('common.seconds') }}</n-tag>
              </div>
            </div>
            <n-empty v-else-if="currentTask && currentTask.status === 'failed'" :description="currentTask.error || 'Failed'" />
            <n-empty v-else :description="t('studio.emptyResult')" />
          </n-spin>
        </n-card>
      </n-gi>
    </n-grid>
  </div>
</template>
