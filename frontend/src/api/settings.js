import client from './client'

export async function getSettings() {
  const { data } = await client.get('/admin/settings')
  return data
}

/** llm_provider, bot_name, welcome_message, extra_instructions */
export async function updateSettings(payload) {
  const { data } = await client.patch('/admin/settings', payload)
  return data
}

export async function saveProviderKey(provider, apiKey) {
  const { data } = await client.put(`/admin/settings/providers/${provider}/api-key`, {
    api_key: apiKey,
  })
  return data
}

export async function deleteProviderKey(provider) {
  await client.delete(`/admin/settings/providers/${provider}/api-key`)
}

export async function updateProviderModel(provider, model) {
  const { data } = await client.patch(`/admin/settings/providers/${provider}`, { model })
  return data
}

export async function listProviderModels(provider) {
  const { data } = await client.get(`/admin/settings/providers/${provider}/models`)
  return data
}

export async function getRagSettings() {
  const { data } = await client.get('/admin/settings/rag')
  return data
}

export async function updateRagSettings(payload) {
  const { data } = await client.patch('/admin/settings/rag', payload)
  return data
}
