import { Link } from "@tanstack/react-router";
import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

export function Logo({ className, to = "/" }: { className?: string; to?: string }) {
  return (
    <Link to={to} className={cn("flex items-center gap-2.5 font-display font-bold", className)}>
      <span className="grid h-8 w-8 place-items-center rounded-lg gradient-primary text-primary-foreground shadow-glow">
        <Sparkles className="h-4 w-4" />
      </span>
      <span className="text-[1.05rem] tracking-tight">
        Etsy Growth <span className="text-gradient">AI</span>
      </span>
    </Link>
  );
}