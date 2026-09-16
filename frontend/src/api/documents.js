import { api } from './client'

/** Tài liệu chương trình (FAQ, hướng dẫn) — nguồn kiến thức của chatbot Tibi. */
export async function fetchDocuments() {
  const { data } = await api.get('/admin/documents')
  return data
}

export async function saveDocument({ documentId, payload }) {
  const { data } = documentId
    ? await api.patch(`/admin/documents/${documentId}`, payload)
    : await api.post('/admin/documents', payload)
  return data
}

export async function deleteDocument(documentId) {
  await api.delete(`/admin/documents/${documentId}`)
}
