<script setup lang="ts">
import { ref } from 'vue'
import { useMessage } from 'naive-ui'
import { useI18n } from 'vue-i18n'
import { createDesign } from '../api'

const message = useMessage()
const { t } = useI18n()

const name = ref('')
const instruct = ref('')
const text = ref('')
const language = ref('zh')
const submitting = ref(false)
const previewUrl = ref('')

const langOptions = [
  { label: t('lang.zh'), value: 'zh' },
  { label: t('lang.en'), value: 'en' },
  { label: t('lang.ja'), value: 'ja' }
]

async function onSubmit() {
  if (!instruct.value.trim()) { message.warning(t('design.instructLabel')); return }
  submitting.value = true
  try {
    await createDesign({
      name: name.value || 'Designed Voice',
      instruct: instruct.value,
      text: text.value || 'こんにちは，你好，hello。',
      language: language.value
    })
    message.success(t('design.success'))
  } catch (e: any) {
    message.error(e?.response?.data?.detail || 'Error')
  } finally {
    submitting.value = false
  }
}
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
  </div>
</template>
