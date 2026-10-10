import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import router from './router'
import i18n from './i18n';
import axiosInstance from './utils/axios';

import {
    // create naive ui
    create,
    // component
    NButton,
    NSelect, 
    NCollapse, 
    NCollapseItem, 
    NMenu, 
    NIcon,
    NLayout,
    NLayoutSider,
    NSplit,
    NImage,
    NAvatar,
    NUpload,
    NMessageProvider,
    NDataTable,
    NRadioGroup,
    NRadioButton,
    NConfigProvider,
    NDescriptions,
    NDescriptionsItem,
    NCard,
    NCarousel,
    NSpace,
    NRadio,
    NLayoutContent,
    NLayoutFooter,
    NLayoutHeader,
    NScrollbar,
    NForm,
    NFormItemGi,
    NGi,
    NGrid,
    NSwitch,
    NTooltip,
    NPopover
  } from 'naive-ui';
import { NInput } from 'naive-ui';
  
  const naive = create({
    components: [
      NButton,
      NSelect, 
      NCollapse, 
      NCollapseItem, 
      NMenu, 
      NIcon,
      NLayout,
      NLayoutSider,
      NLayoutContent,
      NLayoutFooter,
      NLayoutHeader,
      NSplit,
      NImage,
      NAvatar,
      NUpload,
      NMessageProvider,
      NDataTable,
      NRadioGroup,
      NRadioButton,
      NConfigProvider,
      NDescriptions,
      NDescriptionsItem,
      NCard,
      NCarousel,
      NCollapseItem,
      NSpace,
      NRadio,
      NInput,
      NScrollbar,
      NForm,
      NFormItemGi,
      NGi,
      NGrid,
      NSwitch,
      NTooltip,
      NPopover
    ]
  })

const app = createApp(App);

app.use(naive);
app.use(router);
app.use(i18n);
app.config.globalProperties.$t = i18n.global.t;
app.config.globalProperties.$global = i18n.global;
app.config.globalProperties.$axios = axiosInstance;
app.mount('#app');