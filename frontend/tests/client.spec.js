import { describe, expect, it } from 'vitest'

import { getErrorMessage } from '@/api/client'

describe('getErrorMessage', () => {
  it('returns the message from the common error format', () => {
    const error = { response: { data: { error: { code: 'X', message: '권한이 없습니다.' } } } }
    expect(getErrorMessage(error)).toBe('권한이 없습니다.')
  })

  it('falls back to a generic message', () => {
    expect(getErrorMessage(new Error('network'))).toContain('일시적인 오류')
  })
})
