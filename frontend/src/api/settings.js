import client from './client'

export async function getSettings() {
  const { data } = await client.get('/admin/settings')
  return data
}

export async function updateSettings(payload) {
  const { data } = await client.patch('/admin/settings', payload)
  return data
}

export async function saveApiKey(apiKey) {
  const { data } = await client.put('/admin/settings/api-key', { api_key: apiKey })
  return data
}

export async function deleteApiKey() {
  await client.delete('/admin/settings/api-key')
}
