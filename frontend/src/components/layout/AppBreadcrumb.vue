<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const title = computed(() => route.meta.title || '首页')
</script>

<template>
  <div class="breadcrumb"><span>工作台</span><i>/</i><strong>{{ title }}</strong></div>
</template>

<style scoped>
.breadcrumb { display: flex; align-items: center; gap: 9px; margin-bottom: 14px; color: #9aa3b1; font-size: 12px; }
.breadcrumb i { font-style: normal; color: #c7cdd6; }
.breadcrumb strong { color: #657083; font-weight: 500; }
</style>

