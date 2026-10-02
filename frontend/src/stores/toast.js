import { defineStore } from 'pinia'

let nextId = 1

export const useToastStore = defineStore('toast', {
  state: () => ({ toasts: [] }),
  actions: {
    show(message, variant = 'success', timeout = 3000) {
      const id = nextId++
      this.toasts.push({ id, message, variant })
      if (timeout) setTimeout(() => this.dismiss(id), timeout)
    },
    dismiss(id) {
      this.toasts = this.toasts.filter((toast) => toast.id !== id)
    },
  },
})
