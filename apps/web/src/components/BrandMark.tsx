import { Headset } from "lucide-react";

import { cn } from "@/lib/utils";

export function BrandMark({ className, size = 40 }: { className?: string; size?: number }) {
  return (
    <div
      className={cn(
        "grid shrink-0 place-items-center rounded-xl text-white shadow-sm",
        "bg-gradient-to-br from-primary to-violet-500",
        className,
      )}
      style={{ width: size, height: size }}
      aria-hidden
    >
      <Headset style={{ width: size * 0.5, height: size * 0.5 }} />
    </div>
  );
}
