import { Loader2 } from "lucide-react";

const variants = {
  primary: "bg-ink text-white hover:bg-ink-2 shadow-lift",
  accent: "bg-lagoon text-white hover:brightness-110 shadow-lift",
  ghost: "bg-transparent text-ink hover:bg-cloud",
  outline: "border border-line bg-white text-ink hover:border-slate/40 hover:bg-cloud",
  light: "bg-white text-ink hover:bg-cloud shadow-lift",
};

export default function Button({
  as: Tag = "button",
  variant = "primary",
  size = "md",
  loading = false,
  icon: Icon,
  className = "",
  children,
  ...props
}) {
  const sizes = {
    sm: "h-9 px-3.5 text-sm gap-1.5 rounded-lg",
    md: "h-11 px-5 text-[15px] gap-2 rounded-xl",
    lg: "h-14 px-7 text-base gap-2.5 rounded-2xl",
  };
  return (
    <Tag
      className={`inline-flex items-center justify-center font-semibold transition-all duration-200 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50 ${variants[variant]} ${sizes[size]} ${className}`}
      disabled={Tag === "button" ? loading || props.disabled : undefined}
      {...props}
    >
      {loading ? <Loader2 className="animate-spin" size={18} /> : Icon ? <Icon size={18} /> : null}
      {children}
    </Tag>
  );
}
