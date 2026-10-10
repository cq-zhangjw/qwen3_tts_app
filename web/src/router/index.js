import { createRouter, createWebHashHistory } from 'vue-router';


const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import("../pages/LoginPage.vue")
  },
  // {
  //   path: '/',
  //   name: 'Home',
  //   component: () => import("../pages/HomePage.vue")
  // },
  {
    path: '/',
    name: 'chat',
    component: () => import("../pages/ChatPage.vue")
  }
];

const router = createRouter({
  history: createWebHashHistory(import.meta.env.BASE_URL),
  routes
});

export default router;