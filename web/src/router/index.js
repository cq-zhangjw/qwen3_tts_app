import { createRouter, createWebHashHistory } from 'vue-router';

const routes = [
  { path: '/', name: 'studio', component: () => import('../pages/StudioPage.vue') },
  { path: '/voices', name: 'voices', component: () => import('../pages/VoicesPage.vue') },
  { path: '/clone', name: 'clone', component: () => import('../pages/ClonePage.vue') },
  { path: '/design', name: 'design', component: () => import('../pages/DesignPage.vue') },
  { path: '/history', name: 'history', component: () => import('../pages/HistoryPage.vue') }
];

const router = createRouter({
  history: createWebHashHistory(import.meta.env.BASE_URL),
  routes
});

export default router;
