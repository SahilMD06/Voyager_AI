import { Star } from "lucide-react";

export default function Stars({ count, size = 14 }) {
  return (
    <span className="inline-flex items-center gap-0.5" aria-label={`${count} star hotel`}>
      {Array.from({ length: 5 }, (_, i) => (
        <Star
          key={i}
          size={size}
          className={i < count ? "fill-marigold text-marigold" : "text-line"}
          aria-hidden="true"
        />
      ))}
    </span>
  );
}
