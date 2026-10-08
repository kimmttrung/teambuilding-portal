export default function StepIntro({ step, eyebrow, title, description, mobileEyebrow, mobileTitle, mobileDescription, compact = false }) {
  return (
    <header className="mb-1 px-1 max-md:p-0">
      <p className="text-eyebrow font-semibold tracking-[0.14em] text-primary uppercase max-md:text-[12px] max-md:tracking-normal max-md:normal-case">
        <span className="max-md:hidden">Bước {step}/5 · {eyebrow}</span>
        <span className="hidden max-md:inline">{mobileEyebrow || eyebrow}</span>
      </p>
        <h2 className={compact
          ? 'mt-1 text-heading-3 text-ink'
          : 'mt-2 max-w-3xl text-[32px] font-bold leading-[1.08] tracking-[-0.7px] text-balance text-ink max-md:text-[30px] max-md:leading-[1.02] max-md:tracking-[-1.2px]'}>
        <span className="max-md:hidden">{title}</span>
        <span className="hidden max-md:inline">{mobileTitle || title}</span>
      </h2>
      {description && <p className={`mt-2 max-w-2xl text-body-sm text-ink-muted max-md:text-[15px] max-md:leading-[1.35] ${mobileDescription === '' ? 'max-md:hidden' : ''}`}><span className="max-md:hidden">{description}</span><span className="hidden max-md:inline">{mobileDescription ?? description}</span></p>}
    </header>
  )
}
