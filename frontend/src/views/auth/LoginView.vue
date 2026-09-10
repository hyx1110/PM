<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const formRef = ref<FormInstance>()
const loading = ref(false)
const form = reactive({ username: '', password: '' })
const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function submit() {
  if (!(await formRef.value?.validate())) return
  loading.value = true
  try {
    await userStore.login(form)
    ElMessage.success('登录成功')
    await router.replace(String(route.query.redirect || '/dashboard'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section class="intro">
      <div class="eyebrow">PROJECT WORKFORCE</div>
      <h1>让项目、任务与人力安排<br />保持在同一节奏</h1>
      <p>统一维护项目计划，按小时预约人力，及时确认冲突，并沉淀执行与评价数据。</p>
      <div class="flow"><span>项目</span><i></i><span>任务</span><i></i><span>排期</span><i></i><span>执行</span><i></i><span>报表</span></div>
    </section>
    <section class="login-panel">
      <div class="card">
        <div class="logo">协</div>
        <h2>欢迎回来</h2>
        <p>登录项目任务与人力协同管理系统</p>
        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @keyup.enter="submit">
          <el-form-item label="用户名" prop="username"><el-input v-model="form.username" size="large" placeholder="请输入用户名" /></el-form-item>
          <el-form-item label="密码" prop="password"><el-input v-model="form.password" size="large" type="password" show-password placeholder="请输入密码" /></el-form-item>
          <el-button type="primary" size="large" :loading="loading" class="submit" @click="submit">登录</el-button>
        </el-form>
        <div class="hint">初始账号请查看根目录 README，首次登录后请立即修改密码。</div>
      </div>
    </section>
  </main>
</template>

<style scoped>
.login-page { display: grid; min-height: 100vh; grid-template-columns: 1.15fr .85fr; background: #eef2f6; }
.intro { display: flex; flex-direction: column; justify-content: center; padding: 9vw; background: #23364b; color: white; }
.eyebrow { margin-bottom: 22px; color: #91aac2; font-size: 11px; font-weight: 700; letter-spacing: .2em; }
.intro h1 { margin: 0; font-size: clamp(36px,4vw,58px); font-weight: 620; letter-spacing: -.04em; line-height: 1.2; }
.intro p { max-width: 600px; margin: 28px 0 42px; color: #c0ccd8; font-size: 16px; line-height: 1.9; }
.flow { display: flex; align-items: center; gap: 11px; color: #d9e2eb; font-size: 12px; }
.flow i { width: 25px; height: 1px; background: #60778e; }
.login-panel { display: grid; place-items: center; padding: 64px; }
.card { width: min(420px,100%); padding: 46px; border: 1px solid #e2e7ec; border-radius: 24px; background: white; box-shadow: 0 24px 60px rgba(38,50,64,.1); }
.logo { display: grid; width: 46px; height: 46px; place-items: center; border-radius: 14px; background: #355f8d; color: white; font-size: 18px; font-weight: 700; }
.card h2 { margin: 28px 0 8px; color: #192438; font-size: 27px; }
.card > p { margin: 0 0 30px; color: #8a94a3; font-size: 13px; }
.submit { width: 100%; margin-top: 8px; border-radius: 10px; background: #355f8d; }
.hint { margin-top: 22px; color: #a2aab6; font-size: 11px; line-height: 1.6; }
</style>

