// Makes the origin of every number visible: dataset, live API or estimate.
const styles = {
  dataset: "bg-sky-soft text-ink",
  estimate: "bg-marigold-soft text-[#8a5a12]",
  forecast: "bg-lagoon-soft text-[#0a6b62]",
  historical: "bg-cloud text-slate",
  unavailable: "bg-alert-soft text-alert",
};
const labels = {
  dataset: "Dataset price",
  estimate: "Estimate",
  forecast: "Live forecast",
  historical: "Last year's record",
  unavailable: "Unavailable",
};

export default function SourceBadge({ kind, label, className = "" }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[kind]} ${className}`}>
      {label || labels[kind]}
    </span>
  );
}
