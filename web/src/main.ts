import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import router from './router'
import i18n from './i18n';
import axiosInstance from './utils/axios';

import {
  create,
  NConfigProvider,
  NMessageProvider,
  NDialogProvider,
  NGlobalStyle,
  NLayout, NLayoutSider, NLayoutHeader, NLayoutContent, NLayoutFooter,
  NMenu, NIcon, NButton, NSpace, NGrid, NGi,
  NCard, NTag, NSelect, NInput, NRadioGroup, NRadio, NRadioButton,
  NDataTable, NUpload, NProgress, NSpin, NTooltip, NPopover, NPopconfirm,
  NEmpty, NBadge, NDivider, NText, NModal, NForm, NFormItem, NScrollbar,
  NAvatar, NGradientText, NStatistic, NList, NListItem
} from 'naive-ui';

const naive = create({
  components: [
    NConfigProvider, NMessageProvider, NDialogProvider, NGlobalStyle,
    NLayout, NLayoutSider, NLayoutHeader, NLayoutContent, NLayoutFooter,
    NMenu, NIcon, NButton, NSpace, NGrid, NGi,
    NCard, NTag, NSelect, NInput, NRadioGroup, NRadio, NRadioButton,
    NDataTable, NUpload, NProgress, NSpin, NTooltip, NPopover, NPopconfirm,
    NEmpty, NBadge, NDivider, NText, NModal, NForm, NFormItem, NScrollbar,
    NAvatar, NGradientText, NStatistic, NList, NListItem
  ]
});

const app = createApp(App);
app.use(naive);
app.use(router);
app.use(i18n);
app.config.globalProperties.$axios = axiosInstance;
app.mount('#app');
