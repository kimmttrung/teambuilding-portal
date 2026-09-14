/**
 * Tibi — linh vật của trợ lý Team Building: robot tròn, má hồng, ăng-ten đội ngôi sao.
 * `mood="thinking"` khi đang trả lời: mắt nhìn lên, miệng tròn.
 */
export default function ChatMascot({ size = 40, mood = 'happy', className = '' }) {
  const thinking = mood === 'thinking'

  return (
    <svg viewBox="0 0 64 64" width={size} height={size} className={className} aria-hidden="true">
      {/* ăng-ten */}
      <path d="M32 15V8" className="stroke-brand-400" strokeWidth="3" strokeLinecap="round" />
      <path
        d="M32 1.5l1.6 3.3 3.6.5-2.6 2.5.6 3.6-3.2-1.7-3.2 1.7.6-3.6-2.6-2.5 3.6-.5z"
        className={`fill-amber-400 ${thinking ? 'animate-pulse' : ''}`}
      />
      {/* tai */}
      <rect x="2.5" y="29" width="7" height="13" rx="3.5" className="fill-brand-400" />
      <rect x="54.5" y="29" width="7" height="13" rx="3.5" className="fill-brand-400" />
      {/* đầu + mặt */}
      <rect x="7" y="14" width="50" height="44" rx="20" className="fill-brand-600" />
      <rect x="13" y="21" width="38" height="30" rx="14" className="fill-brand-50" />
      {/* mắt */}
      {thinking ? (
        <>
          <circle cx="25" cy="32" r="3.2" className="fill-brand-900" />
          <circle cx="39" cy="32" r="3.2" className="fill-brand-900" />
          <circle cx="26" cy="31" r="1" className="fill-white" />
          <circle cx="40" cy="31" r="1" className="fill-white" />
        </>
      ) : (
        <>
          <path d="M21.5 34q3.5-5 7 0" className="stroke-brand-900" strokeWidth="3" fill="none" strokeLinecap="round" />
          <path d="M35.5 34q3.5-5 7 0" className="stroke-brand-900" strokeWidth="3" fill="none" strokeLinecap="round" />
        </>
      )}
      {/* má hồng */}
      <ellipse cx="19.5" cy="40" rx="3.2" ry="2.2" className="fill-rose-300" />
      <ellipse cx="44.5" cy="40" rx="3.2" ry="2.2" className="fill-rose-300" />
      {/* miệng */}
      {thinking ? (
        <circle cx="32" cy="42" r="2.2" className="fill-brand-900" />
      ) : (
        <path d="M28 40.5q4 4.5 8 0" className="stroke-brand-900" strokeWidth="2.6" fill="none" strokeLinecap="round" />
      )}
    </svg>
  )
}
