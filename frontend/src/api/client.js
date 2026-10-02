import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

const FALLBACK_MESSAGE = '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.'

let authToken = null
let onUnauthorized = null

/** Called by the auth store whenever the token changes. */
export function setAuthToken(token) {
  authToken = token
}

/** Register a callback for 401 responses (the auth store clears its state). */
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler
}

client.interceptors.request.use((config) => {
  if (authToken) {
    config.headers.Authorization = `Token ${authToken}`
  }
  return config
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    // A 401 on login just means wrong credentials, not an expired session.
    const isLogin = error.config?.url === '/auth/login'
    if (error.response?.status === 401 && !isLogin && onUnauthorized) {
      onUnauthorized()
    }
    return Promise.reject(error)
  },
)

/** Extract the user-facing message from the common error format (specs/04-api.md). */
export function getErrorMessage(error) {
  return error?.response?.data?.error?.message || FALLBACK_MESSAGE
}

/** Field errors from a VALIDATION_ERROR response: { field: 'first message' }. */
export function getFieldErrors(error) {
  const details = error?.response?.data?.error?.details || {}
  return Object.fromEntries(
    Object.entries(details).map(([field, messages]) => [
      field,
      Array.isArray(messages) ? messages[0] : String(messages),
    ]),
  )
}

export default client
