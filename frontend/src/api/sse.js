/**
 * Incremental parser for `data: <json>\n\n` server-sent events (specs/04 §7).
 * Chunks may split events (or multi-byte characters) anywhere; feed them as they arrive.
 */
export function createSseParser(onEvent) {
  const decoder = new TextDecoder()
  let buffer = ''

  function flushEvents() {
    let boundary
    while ((boundary = buffer.indexOf('\n\n')) !== -1) {
      const raw = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      const data = raw
        .split('\n')
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trimStart())
        .join('\n')
      if (data) onEvent(JSON.parse(data))
    }
  }

  return {
    push(chunk) {
      buffer += typeof chunk === 'string' ? chunk : decoder.decode(chunk, { stream: true })
      flushEvents()
    },
    end() {
      buffer += decoder.decode()
      if (buffer.trim()) buffer += '\n\n'
      flushEvents()
    },
  }
}
