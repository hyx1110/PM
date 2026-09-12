import { ref } from 'vue'
import { defineStore } from 'pinia'
import { getUnreadCount } from '@/api/notification'

export const useNotificationStore = defineStore('notification', () => {
  const unreadCount = ref(0)

  async function refreshUnreadCount() {
    try {
      unreadCount.value = (await getUnreadCount()).count
    } catch {
      // Keep the last known value when the count request temporarily fails.
    }
  }

  function markOneRead() {
    unreadCount.value = Math.max(unreadCount.value - 1, 0)
  }

  function markAllRead() {
    unreadCount.value = 0
  }

  return { unreadCount, refreshUnreadCount, markOneRead, markAllRead }
})
