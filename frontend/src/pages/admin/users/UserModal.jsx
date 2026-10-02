import Modal from '../../../components/common/Modal'
import '../../../components/profile/F1Surface.css'

/** Scope giao diện F1, không thay đổi Modal dùng chung của các nhóm khác. */
export default function UserModal({ drawer = false, ...props }) {
  return <div className={`f1-surface f1-modal ${drawer ? 'f1-drawer' : ''}`}><Modal {...props} /></div>
}
