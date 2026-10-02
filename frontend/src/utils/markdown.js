/**
 * Markdown -> sanitized HTML for chatbot answers (specs/06 §5.1, specs/07 §5).
 *
 * LLM output is untrusted (it can echo retrieved documents), so the HTML from marked
 * always goes through DOMPurify with a small formatting-only allowlist. Images, iframes,
 * forms and styles are dropped (no tracking pixels / exfiltration via image URLs),
 * and links may only be http(s), mailto or tel and open in a new tab.
 */
import DOMPurify from 'dompurify'
import { Marked } from 'marked'

const markdown = new Marked({ gfm: true, breaks: true, async: false })

const SANITIZE_OPTIONS = {
  ALLOWED_TAGS: [
    'p',
    'br',
    'strong',
    'b',
    'em',
    'i',
    'del',
    's',
    'ul',
    'ol',
    'li',
    'blockquote',
    'hr',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'code',
    'pre',
    'table',
    'thead',
    'tbody',
    'tr',
    'th',
    'td',
    'a',
  ],
  ALLOWED_ATTR: ['href', 'title'],
  ALLOWED_URI_REGEXP: /^(?:https?:|mailto:|tel:)/i,
}

DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A') {
    if (!node.getAttribute('href')) {
      node.removeAttribute('title') // stays as plain text-like inline element
    }
    node.setAttribute('target', '_blank')
    node.setAttribute('rel', 'noopener noreferrer nofollow')
  }
})

export function renderMarkdown(text) {
  if (!text) return ''
  return DOMPurify.sanitize(markdown.parse(text), SANITIZE_OPTIONS)
}
