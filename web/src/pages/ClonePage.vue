<script setup lang="ts">
import { ref } from 'vue'
import { useMessage } from 'naive-ui'
import { useI18n } from 'vue-i18n'
import { createClone } from '../api'

const message = useMessage()
const { t } = useI18n()

const name = ref('')
const refText = ref('')
const fileList = ref<any[]>([])
const submitting = ref(false)
const createdId = ref('')

function handleUpload({ file, fileList: fl }: any) {
  fileList.value = fl
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
    const res = await createClone(fd)
    createdId.value = res.data.id
    message.success(t('clone.success'))
    name.value = ''; refText.value = ''; fileList.value = []
  } catch (e: any) {
    message.error(e?.response?.data?.detail || 'Error')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="page-wrap" style="max-width:680px">
    <div class="section-title">{{ t('clone.title') }}</div>
    <div style="color:#64748b; font-size:13px; margin-bottom:16px">{{ t('clone.desc') }}</div>

    <n-card bordered>
      <n-form label-placement="top">
        <n-form-item :label="t('clone.uploadLabel')">
          <n-upload
            :file-list="fileList"
            :max="1"
            accept=".wav,.mp3,.m4a"
            @change="handleUpload"
          >
            <n-button>{{ t('clone.uploadLabel') }}</n-button>
            <template #tip>
              <div style="color:#94a3b8; font-size:12px">{{ t('clone.uploadHint') }}</div>
            </template>
          </n-upload>
        </n-form-item>

        <n-form-item :label="t('common.name')">
          <n-input v-model:value="name" :placeholder="t('clone.namePlaceholder')" />
        </n-form-item>

        <n-form-item :label="t('clone.refTextLabel')">
          <n-input
            v-model:value="refText"
            type="textarea"
            :rows="4"
            :placeholder="t('clone.refTextPlaceholder')"
          />
        </n-form-item>

        <n-button type="primary" block :loading="submitting" @click="onSubmit">
          {{ t('clone.submit') }}
        </n-button>
      </n-form>
    </n-card>
  </div>
</template>
