<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NIcon } from 'naive-ui'
import {
  MicOutline, PeopleOutline, CopyOutline, ColorWandOutline,
  TimeOutline, LanguageOutline, SparklesOutline
} from '@vicons/ionicons5'
import { getSystemInfo } from './api'

const route = useRoute()
const router = useRouter()
const { locale, t } = useI18n()

const collapsed = ref(false)
const modelLoaded = ref<Record<string, boolean>>({})
const gpuName = ref('')

const currentKey = computed(() => route.name as string)

const menuItems = computed(() => [
  { label: t('nav.studio'), key: 'studio', icon: () => h(NIcon, null, { default: () => h(MicOutline) }) },
  { label: t('nav.voices'), key: 'voices', icon: () => h(NIcon, null, { default: () => h(PeopleOutline) }) },
  { label: t('nav.clone'), key: 'clone', icon: () => h(NIcon, null, { default: () => h(CopyOutline) }) },
  { label: t('nav.design'), key: 'design', icon: () => h(NIcon, null, { default: () => h(ColorWandOutline) }) },
  { label: t('nav.history'), key: 'history', icon: () => h(NIcon, null, { default: () => h(TimeOutline) }) }
])

const langOptions = [
  { label: '中文', value: 'zh' },
  { label: 'English', value: 'en' },
  { label: '日本語', value: 'ja' }
]

function onSelect(key: string) {
  router.push({ name: key })
}

function onLangChange(v: string) {
  locale.value = v
  localStorage.setItem('locale', v)
}

onMounted(async () => {
  try {
    const { data } = await getSystemInfo()
    modelLoaded.value = data.models_loaded || {}
    gpuName.value = data.gpu_name || ''
  } catch (e) { /* backend may be starting */ }
})
</script>

<template>
  <n-config-provider :theme-overrides="{
    common: {
      primaryColor: '#6366f1',
      primaryColorHover: '#818cf8',
      primaryColorPressed: '#4f46e5',
      borderRadius: '10px',
      borderRadiusSmall: '8px'
    }
  }">
    <n-message-provider>
      <n-dialog-provider>
        <n-layout has-sider style="height: 100vh">
          <n-layout-sider
            bordered
            collapse-mode="width"
            :collapsed-width="64"
            :width="220"
            :collapsed="collapsed"
            show-trigger
            trigger-position="header"
            style="background: linear-gradient(180deg, #1e1b4b 0%, #312e81 100%)"
          >
            <div style="display:flex; align-items:center; gap:10px; padding:18px 16px; color:#fff">
              <n-icon size="22" color="#a5b4fc"><sparkles-outline /></n-icon>
              <span v-if="!collapsed" style="font-weight:700; font-size:16px">{{ t('app.name') }}</span>
            </div>
            <n-menu
              :value="currentKey"
              :items="menuItems"
              @update:value="onSelect"
              style="background: transparent; color:#e0e7ff"
            />
          </n-layout-sider>

          <n-layout>
            <n-layout-header bordered style="padding: 0 20px; height: 56px; display:flex; align-items:center; justify-content:space-between; background:#fff">
              <div style="font-weight:600; color:#334155">{{ t(`nav.${currentKey}`) }}</div>
              <div style="display:flex; align-items:center; gap:14px">
                <n-tag size="small" :bordered="false" type="info">
                  {{ t('header.modelStatus') }}: {{ Object.values(modelLoaded).some(Boolean) ? t('header.loaded') : t('header.notLoaded') }}
                </n-tag>
                <n-select
                  :value="locale"
                  :options="langOptions"
                  style="width: 120px"
                  size="small"
                  @update:value="onLangChange"
                >
                  <template #prefix>
                    <n-icon><language-outline /></n-icon>
                  </template>
                </n-select>
              </div>
            </n-layout-header>

            <n-layout-content style="overflow-y: auto; background:#f5f7fa">
              <router-view />
            </n-layout-content>

            <n-layout-footer style="text-align:center; padding:12px; color:#94a3b8; font-size:12px">
              Qwen3 TTS Studio · {{ gpuName }}
            </n-layout-footer>
          </n-layout>
        </n-layout>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>
