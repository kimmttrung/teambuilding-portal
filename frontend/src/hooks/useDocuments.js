import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { deleteDocument, fetchDocuments, saveDocument } from '../api/documents'
import { QUERY_KEYS } from '../utils/constants'

/**
 * Tài liệu chương trình (FAQ, hướng dẫn) — nguồn kiến thức của chatbot Tibi.
 *
 * Ghi xong phải dọn cả `ragStatus`: backend hạ `is_indexed` về false, thẻ Tibi trên dashboard dựa vào
 * đó để nhắc BTC nạp lại kiến thức. Không dọn thì thẻ vẫn báo "đã nạp" trong khi tài liệu đã đổi.
 */
export function useDocuments({ enabled = true } = {}) {
  return useQuery({ queryKey: QUERY_KEYS.documents, queryFn: fetchDocuments, enabled })
}

function useDocumentSync() {
  const queryClient = useQueryClient()
  return {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.documents })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ragStatus })
    },
  }
}

export function useSaveDocument() {
  return useMutation({ mutationFn: saveDocument, ...useDocumentSync() })
}

export function useDeleteDocument() {
  return useMutation({ mutationFn: deleteDocument, ...useDocumentSync() })
}
