import Modal from '../../../components/common/Modal'
import '../../../components/profile/F1Surface.css'

/** Scope giao diện F1, không thay đổi Modal dùng chung của các nhóm khác. */
export default function UserModal(props) {
  return <div className="f1-surface f1-modal"><Modal {...props} /></div>
}
