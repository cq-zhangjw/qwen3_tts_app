<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import { useMessage } from 'naive-ui'
import { useI18n } from 'vue-i18n'
import { createDesign, listVoices } from '../api'

const message = useMessage()
const { t } = useI18n()

const name = ref('')
const instruct = ref('')
const text = ref('')
const language = ref('zh')
const submitting = ref(false)
const resultVoice = ref<any>(null)
const playingKey = ref<string | null>(null)
let timer: number | null = null

const langOptions = [
  { label: t('lang.zh'), value: 'zh' },
  { label: t('lang.en'), value: 'en' },
  { label: t('lang.ja'), value: 'ja' }
]

async function onSubmit() {
  if (!instruct.value.trim()) { message.warning(t('design.instructLabel')); return }
  submitting.value = true
  resultVoice.value = null
  try {
    const res = await createDesign({
      name: name.value || 'Designed Voice',
      instruct: instruct.value,
      text: text.value || 'こんにちは，你好，hello。',
      language: language.value
    })
    message.success(t('design.success'))
    pollResult(res.data.id)
  } catch (e: any) {
    message.error(e?.response?.data?.detail || 'Error')
  } finally {
    submitting.value = false
  }
}

function pollResult(vid: string) {
  let tries = 0
  timer = window.setInterval(async () => {
    tries++
    try {
      const res = await listVoices({ type: 'design' })
      const v = (res.data || []).find((x: any) => x.id === vid)
      if (v && v.status === 'ready') {
        resultVoice.value = v
        if (timer) clearInterval(timer)
      } else if (v && v.status === 'failed') {
        message.error(v.error || 'failed')
        if (timer) clearInterval(timer)
      }
    } catch { /* ignore */ }
    if (tries > 40 && timer) clearInterval(timer)
  }, 2000)
}

function play(key: string, url?: string) {
  if (!url) return
  if (playingKey.value === key) return
  playingKey.value = key
  const audio = new Audio(url)
  audio.onended = () => (playingKey.value = null)
  audio.play()
}

onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<template>
  <div class="page-wrap" style="max-width:680px">
    <div class="section-title">{{ t('design.title') }}</div>
    <div style="color:#64748b; font-size:13px; margin-bottom:16px">{{ t('design.desc') }}</div>

    <n-card bordered>
      <n-form label-placement="top">
        <n-form-item :label="t('common.name')">
          <n-input v-model:value="name" :placeholder="t('design.namePlaceholder')" />
        </n-form-item>

        <n-form-item :label="t('design.instructLabel')">
          <n-input
            v-model:value="instruct"
            type="textarea"
            :rows="3"
            :placeholder="t('design.instructPlaceholder')"
          />
        </n-form-item>

        <n-form-item :label="t('design.textLabel')">
          <n-input
            v-model:value="text"
            type="textarea"
            :rows="3"
            :placeholder="t('design.textPlaceholder')"
          />
        </n-form-item>

        <n-form-item :label="t('design.languageLabel')">
          <n-select v-model:value="language" :options="langOptions" style="width:180px" />
        </n-form-item>

        <n-button type="primary" block :loading="submitting" @click="onSubmit">
          {{ t('design.submit') }}
        </n-button>
      </n-form>
    </n-card>

    <n-card v-if="resultVoice" bordered class="mt-16" :title="resultVoice.name">
      <n-grid :cols="3" :responsive="['screen']" :x-gap="12">
        <n-gi v-for="L of ['zh','ja','en']" :key="L">
          <n-button block :loading="playingKey === L"
            @click="play(L, resultVoice[`audio_url_${L}`])">
            {{ t(`lang.${L}`) }} ▶
          </n-button>
        </n-gi>
      </n-grid>
      <div style="color:#94a3b8; font-size:11px; margin-top:10px">
        中/日/英三段试听已生成，可在混合合成中保持同一音色。
      </div>
    </n-card>
  </div>
</template>
