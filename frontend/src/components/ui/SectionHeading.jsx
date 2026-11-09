export default function SectionHeading({ id, title, intro, action }) {
  return (
    <div id={id} className="mb-6 flex scroll-mt-24 flex-wrap items-end justify-between gap-4">
      <div className="max-w-2xl">
        <h2 className="text-2xl text-ink md:text-[28px]">{title}</h2>
        {intro && <p className="mt-1.5 text-slate">{intro}</p>}
      </div>
      {action}
    </div>
  );
}
