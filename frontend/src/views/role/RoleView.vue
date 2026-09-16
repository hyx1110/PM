<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getPermissions, getRoles, updateRolePermissions } from '@/api/role'
import type { Permission, Role } from '@/types/role'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const roles = ref<Role[]>([])
const permissions = ref<Permission[]>([])
const selectedRoleId = ref<number>()
const selectedPermissions = ref<number[]>([])
const loading = ref(false)
const selectedRole = computed(() => roles.value.find((item) => item.id === selectedRoleId.value))
const groups = computed(() => permissions.value.reduce<Record<string, Permission[]>>((result, item) => {
  ;(result[item.module] ||= []).push(item)
  return result
}, {}))

async function load() {
  loading.value = true
  try {
    ;[roles.value, permissions.value] = await Promise.all([getRoles(), getPermissions()])
    selectRole(roles.value[0])
  } finally { loading.value = false }
}
function selectRole(role?: Role) { if (!role) return; selectedRoleId.value = role.id; selectedPermissions.value = [...role.permission_ids] }
async function save() {
  if (!selectedRoleId.value) return
  await updateRolePermissions(selectedRoleId.value, selectedPermissions.value)
  ElMessage.success('角色权限已更新')
  await load()
  selectRole(roles.value.find((item) => item.id === selectedRoleId.value))
}
onMounted(load)
</script>

<template>
  <div class="page-shell">
    <header class="page-header"><div><h1 class="page-title">角色权限</h1><p class="page-subtitle">统一维护超级管理员、L3、L4、项目经理和项目成员五类系统角色的功能权限。</p></div><el-button v-if="userStore.hasPermission('role:edit')" type="primary" :disabled="!selectedRole" @click="save">保存权限</el-button></header>
    <section class="permission-layout" v-loading="loading">
      <aside class="surface role-list"><button v-for="role in roles" :key="role.id" :class="{active:selectedRoleId===role.id}" @click="selectRole(role)"><div><strong>{{ role.name }}</strong><small>{{ role.code }}</small></div><span>{{ role.permission_ids.length }}</span></button></aside>
      <main class="surface permission-card">
        <div class="permission-head"><div><h2>{{ selectedRole?.name || '请选择角色' }}</h2><p>{{ selectedRole?.description || '勾选该角色可以访问的功能。' }}</p></div><el-tag v-if="selectedRole?.is_system" effect="plain">系统角色</el-tag></div>
        <el-checkbox-group v-model="selectedPermissions" :disabled="!userStore.hasPermission('role:edit') || selectedRole?.code==='super_admin'">
          <section v-for="(items,module) in groups" :key="module" class="permission-group"><h3>{{ module }}</h3><div class="permission-grid"><label v-for="item in items" :key="item.id" class="permission-item"><el-checkbox :value="item.id"><span>{{ item.name }}</span><small>{{ item.code }}</small></el-checkbox></label></div></section>
        </el-checkbox-group>
      </main>
    </section>
  </div>
</template>

<style scoped>
.permission-layout{display:grid;grid-template-columns:280px 1fr;gap:16px;min-height:620px}.role-list{padding:12px}.role-list button{display:flex;width:100%;align-items:center;justify-content:space-between;border:0;border-radius:11px;background:transparent;padding:14px;text-align:left;cursor:pointer}.role-list button.active{background:#edf3f9}.role-list strong,.role-list small{display:block}.role-list strong{color:#364357;font-size:14px}.role-list small{margin-top:4px;color:#9ba4b2;font-size:10px}.role-list button>span{display:grid;width:25px;height:25px;place-items:center;border-radius:50%;background:#f0f2f5;color:#687487;font-size:11px}.permission-card{padding:28px}.permission-head{display:flex;align-items:start;justify-content:space-between;padding-bottom:22px;border-bottom:1px solid #edf0f3}.permission-head h2{margin:0;color:#273448;font-size:20px}.permission-head p{margin:7px 0 0;color:#919ba9;font-size:12px}.permission-group{padding:20px 0 6px;border-bottom:1px solid #f0f2f5}.permission-group h3{margin:0 0 14px;color:#6f7a8a;font-size:11px;text-transform:uppercase}.permission-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.permission-item{padding:12px;border:1px solid #edf0f3;border-radius:10px}.permission-item span,.permission-item small{display:block}.permission-item span{color:#3f4c5f}.permission-item small{margin-top:2px;color:#a0a8b4;font-size:10px}
</style>
