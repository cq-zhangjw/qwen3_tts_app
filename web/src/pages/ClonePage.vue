<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import { useMessage } from 'naive-ui'
import { useI18n } from 'vue-i18n'
import { createClone } from '../api'

const message = useMessage()
const { t } = useI18n()

const name = ref('')
const language = ref('zh')
const refText = ref('')
const fileList = ref<any[]>([])
const submitting = ref(false)
const recording = ref(false)
const recordedUrl = ref('')
let mediaRecorder: MediaRecorder | null = null
let chunks: Blob[] = []

const PRESET_TEXTS: Record<string, string> = {
  zh: '你好，今天天气真不错，我们一起出去走走吧。',
  en: 'Hello, the weather is really nice today. Let\'s go out for a walk together.',
  ja: 'こんにちは、今日はとてもいい天気ですね。一緒に出かけましょう。'
}
const langOptions = [
  { label: '中文', value: 'zh' },
  { label: 'English', value: 'en' },
  { label: '日本語', value: 'ja' }
]

function applyPreset() {
  refText.value = PRESET_TEXTS[language.value]
}

async function toggleRecord() {
  if (recording.value) {
    mediaRecorder?.stop()
    return
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    chunks = []
    mediaRecorder = new MediaRecorder(stream)
    mediaRecorder.ondataavailable = (e) => chunks.push(e.data)
    mediaRecorder.onstop = () => {
      const blob = new Blob(chunks, { type: 'audio/webm' })
      recordedUrl.value = URL.createObjectURL(blob)
      const file = new File([blob], 'record.webm', { type: 'audio/webm' })
      fileList.value = [{ file }]
      recording.value = false
      stream.getTracks().forEach(t => t.stop())
    }
    mediaRecorder.start()
    recording.value = true
  } catch (e: any) {
    message.error('无法访问麦克风：' + (e?.message || e))
  }
}

function handleUpload({ fileList: fl }: any) {
  fileList.value = fl
  recordedUrl.value = ''
}

async function onSubmit() {
  if (!fileList.value.length) { message.warning(t('clone.needFile')); return }
  if (!refText.value.trim()) { message.warning(t('clone.needRefText')); return }
  submitting.value = true
  try {
    const fd = new FormData()
    fd.append('file', fileList.value[0].file)
    fd.append('name', name.value || 'Clone Voice')
    fd.append('ref_text', refText.value)
    fd.append('language', language.value)
    await createClone(fd)
    message.success(t('clone.success'))
    name.value = ''; refText.value = ''; fileList.value = []; recordedUrl.value = ''
  } catch (e: any) {
    message.error(e?.response?.data?.detail || 'Error')
  } finally {
    submitting.value = false
  }
}

onUnmounted(() => { mediaRecorder?.stop() })
</script>

<template>
  <div class="page-wrap" style="max-width:680px">
    <div class="section-title">{{ t('clone.title') }}</div>
    <div style="color:#64748b; font-size:13px; margin-bottom:16px">{{ t('clone.desc') }}</div>

    <n-card bordered>
      <n-form label-placement="top">
        <n-form-item :label="t('common.language')">
          <n-space align="center">
            <n-select v-model:value="language" :options="langOptions" style="width:140px" @update:value="applyPreset" />
            <n-button size="small" @click="applyPreset">{{ t('clone.usePreset') }}</n-button>
          </n-space>
        </n-form-item>

        <n-form-item :label="t('common.name')">
          <n-input v-model:value="name" :placeholder="t('clone.namePlaceholder')" />
        </n-form-item>

        <n-form-item :label="t('clone.refTextLabel')">
          <n-input v-model:value="refText" type="textarea" :rows="3" :placeholder="t('clone.refTextPlaceholder')" />
          <div style="color:#94a3b8; font-size:11px; margin-top:6px">{{ PRESET_TEXTS[language] }}</div>
        </n-form-item>

        <n-form-item :label="t('clone.audioSource')">
          <n-space>
            <n-button type="error" :ghost="!recording" @click="toggleRecord">
              {{ recording ? t('clone.stopRec') : t('clone.startRec') }}
            </n-button>
            <n-upload :file-list="fileList" :max="1" accept=".wav,.mp3,.m4a,.webm" @change="handleUpload">
              <n-button>{{ t('clone.uploadLabel') }}</n-button>
            </n-upload>
          </n-space>
          <audio v-if="recordedUrl" :src="recordedUrl" controls style="margin-top:10px; width:100%" />
        </n-form-item>

        <n-button type="primary" block :loading="submitting" @click="onSubmit">
          {{ t('clone.submit') }}
        </n-button>
      </n-form>
    </n-card>
  </div>
</template>
