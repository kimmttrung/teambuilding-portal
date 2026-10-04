import { useState } from 'react'
import { Save } from 'lucide-react'
import Button from '../../../components/common/Button'
import Modal from '../../../components/common/Modal'
import AnnouncementForm from './AnnouncementForm'

const FORM_ID = 'announcement-edit-form'

/**
 * Sửa một thông báo đã có (nháp hoặc đã đăng). Soạn mới nằm ngay trên trang, ở thẻ "Thông báo mới";
 * cả hai dùng chung `AnnouncementForm` nên luật chọn đối tượng chỉ viết một lần.
 */
export default function AnnouncementFormModal({ open, onClose, item }) {
  const [pending, setPending] = useState(false)

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title={item ? 'Sửa thông báo' : 'Soạn thông báo mới'}
      description={
        item?.published_at ? 'Đang hiện với CBNV — lưu là họ thấy nội dung mới ngay' : 'Bản nháp, chỉ BTC thấy'
      }
      footer={
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>
            Huỷ
          </Button>
          <Button type="submit" form={FORM_ID} size="sm" icon={Save} loading={pending}>
            {item ? 'Lưu thay đổi' : 'Lưu nháp'}
          </Button>
        </div>
      }
    >
      <AnnouncementForm formId={FORM_ID} item={item} active={open} onSaved={onClose} onPendingChange={setPending} />
    </Modal>
  )
}
