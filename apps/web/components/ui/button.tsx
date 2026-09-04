import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";
export function Button({className,...props}:ButtonHTMLAttributes<HTMLButtonElement>){return <button className={cn("rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700 focus-visible:outline-2 dark:bg-slate-100 dark:text-slate-950",className)} {...props}/>}
