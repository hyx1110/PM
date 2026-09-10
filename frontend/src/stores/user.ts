import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import * as authApi from '@/api/auth'
import { TOKEN_KEY } from '@/api/request'
import type { CurrentUser, LoginPayload } from '@/types/auth'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem(TOKEN_KEY) || '')
  const profile = ref<CurrentUser | null>(null)
  const loaded = ref(false)
  const isLoggedIn = computed(() => Boolean(token.value))

  function hasPermission(permission?: string): boolean {
    if (!permission) return true
    return profile.value?.roles.includes('super_admin') || profile.value?.permissions.includes(permission) || false
  }

  async function login(payload: LoginPayload) {
    const result = await authApi.login(payload)
    token.value = result.access_token
    profile.value = result.user
    loaded.value = true
    localStorage.setItem(TOKEN_KEY, result.access_token)
  }

  async function fetchProfile() {
    if (!token.value) return null
    profile.value = await authApi.getCurrentUser()
    loaded.value = true
    return profile.value
  }

  async function logout() {
    try {
      if (token.value) await authApi.logout()
    } catch {
      // Local logout must still complete when the token is already invalid.
    } finally {
      token.value = ''
      profile.value = null
      loaded.value = false
      localStorage.removeItem(TOKEN_KEY)
    }
  }

  return { token, profile, loaded, isLoggedIn, hasPermission, login, fetchProfile, logout }
})
