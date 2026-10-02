import { describe, expect, it, vi } from 'vitest'

import client, {
  getErrorMessage,
  getFieldErrors,
  setAuthToken,
  setUnauthorizedHandler,
} from '@/api/client'

describe('getErrorMessage', () => {
  it('returns the message from the common error format', () => {
    const error = { response: { data: { error: { code: 'X', message: '권한이 없습니다.' } } } }
    expect(getErrorMessage(error)).toBe('권한이 없습니다.')
  })

  it('falls back to a generic message', () => {
    expect(getErrorMessage(new Error('network'))).toContain('일시적인 오류')
  })
})

describe('getFieldErrors', () => {
  it('maps details to the first message per field', () => {
    const error = { response: { data: { error: { details: { name: ['필수', '두번째'] } } } } }
    expect(getFieldErrors(error)).toEqual({ name: '필수' })
  })
})

describe('interceptors', () => {
  it('adds the token header when set', async () => {
    setAuthToken('abc')
    const config = await client.interceptors.request.handlers[0].fulfilled({ headers: {} })
    expect(config.headers.Authorization).toBe('Token abc')
    setAuthToken(null)
  })

  it('calls the unauthorized handler on 401 except for login', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    const onError = client.interceptors.response.handlers[0].rejected

    await expect(
      onError({ config: { url: '/auth/me' }, response: { status: 401 } }),
    ).rejects.toBeTruthy()
    await expect(
      onError({ config: { url: '/auth/login' }, response: { status: 401 } }),
    ).rejects.toBeTruthy()

    expect(handler).toHaveBeenCalledTimes(1)
  })
})
