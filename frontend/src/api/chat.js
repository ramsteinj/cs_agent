import client from './client'

export async function fetchStatus() {
  const { data } = await client.get('/chat/status')
  return data
}
