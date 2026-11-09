export default function Skeleton({ className = "" }) {
  return <div className={`animate-pulse rounded-xl bg-cloud ${className}`} aria-hidden="true" />;
}
