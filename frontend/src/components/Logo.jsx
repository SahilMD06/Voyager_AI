export default function Logo({ light = false, size = 32 }) {
  return (
    <span className="flex items-center gap-2.5">
      <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
        <rect width="32" height="32" rx="9" fill={light ? "#ffffff" : "#0E2240"} />
        <path
          d="M7 20.5c4.5-8 13.5-12 18-11-3 1.5-6.5 5.5-8 11"
          fill="none"
          stroke="#4AA3E8"
          strokeWidth="2.6"
          strokeLinecap="round"
        />
        <circle cx="17" cy="21" r="2.4" fill="#0F9C8F" />
      </svg>
      <span className={`font-display text-[21px] font-bold tracking-tight ${light ? "text-white" : "text-ink"}`}>
        Voyager<span className="font-medium opacity-60"> AI</span>
      </span>
    </span>
  );
}
