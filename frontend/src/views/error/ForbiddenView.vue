<template>
  <div class="surface forbidden"><strong>403</strong><h1>没有访问权限</h1><p>当前角色没有访问此页面所需的权限。</p><el-button type="primary" @click="$router.push('/')">返回首页</el-button></div>
</template>

<style scoped>
.forbidden { display: grid; min-height: 420px; place-items: center; align-content: center; text-align: center; }
.forbidden strong { color: #dce4ec; font-size: 80px; line-height: 1; }
.forbidden h1 { margin: 18px 0 8px; color: #26364a; }
.forbidden p { margin: 0 0 24px; color: #8b95a3; }
</style>

