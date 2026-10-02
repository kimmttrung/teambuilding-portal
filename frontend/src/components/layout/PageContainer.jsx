/** Container chuẩn cho vùng nội dung các tab người dùng, dùng toàn bộ chiều ngang khả dụng. */
export default function PageContainer({ children, className = '' }) {
  return <div className={`w-full ${className}`}>{children}</div>
}
