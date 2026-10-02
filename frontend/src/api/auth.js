import client from './client'

export async function login(username, password) {
  const { data } = await client.post('/auth/login', { username, password })
  return data
}

export async function logout() {
  await client.post('/auth/logout')
}

export async function fetchMe() {
  const { data } = await client.get('/auth/me')
  return data
}

export async function changePassword(currentPassword, newPassword) {
  const { data } = await client.post('/auth/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  })
  return data
}
