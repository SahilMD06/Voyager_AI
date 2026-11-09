import { Cloud, CloudDrizzle, CloudFog, CloudLightning, CloudRain, CloudSun, HelpCircle, Snowflake, Sun } from "lucide-react";

const map = {
  sun: { Icon: Sun, color: "text-marigold" },
  "cloud-sun": { Icon: CloudSun, color: "text-sky" },
  cloud: { Icon: Cloud, color: "text-slate" },
  fog: { Icon: CloudFog, color: "text-mist" },
  drizzle: { Icon: CloudDrizzle, color: "text-sky" },
  rain: { Icon: CloudRain, color: "text-sky" },
  snow: { Icon: Snowflake, color: "text-sky" },
  storm: { Icon: CloudLightning, color: "text-ink" },
  unknown: { Icon: HelpCircle, color: "text-mist" },
};

export default function WeatherIcon({ icon, size = 22, className = "" }) {
  const { Icon, color } = map[icon] || map.unknown;
  return <Icon size={size} className={`${color} ${className}`} aria-hidden="true" />;
}
