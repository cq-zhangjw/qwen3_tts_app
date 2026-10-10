<script setup lang="ts">

</script>

<template>
  <div id="app">
    <n-config-provider>
      <n-message-provider>
        <router-view></router-view>
      </n-message-provider>
    </n-config-provider>
  </div>
</template>

<style scoped>
  #app {
    /* min-width: 850px; */
  }
</style>
