import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

const FALLBACK_MESSAGE = '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.'

/** Extract the user-facing message from the common error format (specs/04-api.md). */
export function getErrorMessage(error) {
  return error?.response?.data?.error?.message || FALLBACK_MESSAGE
}

export default client
