import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 0
})

// ---- system ----
export const getSystemInfo = () => api.get('/system/info').then(r => r.data)

// ---- voices ----
export const listVoices = (params?: { type?: string; keyword?: string }) =>
  api.get('/voices', { params }).then(r => r.data)
export const getVoice = (id: string) => api.get(`/voices/${id}`).then(r => r.data)
export const deleteVoice = (id: string) => api.delete(`/voices/${id}`).then(r => r.data)
export const createClone = (form: FormData) =>
  api.post('/voices/clone', form).then(r => r.data)
export const createDesign = (body: { name: string; instruct: string; text: string; language: string }) =>
  api.post('/voices/design', body).then(r => r.data)

// ---- tts ----
export const createTask = (body: { text: string; voice_id: string; language: string; instruct?: string | null }) =>
  api.post('/tts', body).then(r => r.data)
export const listTasks = (params?: { page?: number; page_size?: number; status?: string; voice_id?: string }) =>
  api.get('/tts/tasks', { params }).then(r => r.data)
export const getTask = (id: string) => api.get(`/tts/tasks/${id}`).then(r => r.data)
export const deleteTask = (id: string) => api.delete(`/tts/tasks/${id}`).then(r => r.data)

// audio url helper
export const audioUrl = (url?: string | null) => (url ? url : '')

export default api
