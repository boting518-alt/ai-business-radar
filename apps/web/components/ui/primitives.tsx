import type { ReactNode } from "react";
export function PageHeader({title,description,actions}:{title:string;description:string;actions?:ReactNode}){return <header className="flex items-start justify-between gap-4"><div><h1 className="text-2xl font-semibold tracking-tight">{title}</h1><p className="mt-1 text-sm text-slate-500">{description}</p></div>{actions}</header>}
export function SectionHeader({children}:{children:ReactNode}){return <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500">{children}</h2>}
export function StatCard({label,value}:{label:string;value:string}){return <div className="rounded-lg border p-4"><p className="text-xs text-slate-500">{label}</p><p className="mt-2 text-2xl tabular-nums">{value}</p></div>}
export function ScoreBadge({label,value}:{label:string;value:number|null}){return <span title="Composite commercial opportunity score" className="inline-flex rounded border border-slate-300 bg-slate-50 px-2 py-1 text-xs font-semibold tabular-nums dark:bg-slate-900">{label&&`${label} `}{value==null?"—":value}</span>}
export function StageBadge({stage}:{stage:string}){return <span className="rounded-full bg-slate-100 px-2 py-1 text-xs dark:bg-slate-800">{stage}</span>}
export function FilterBar({children}:{children?:ReactNode}){return <div className="rounded-lg border bg-white p-3 dark:bg-slate-950">{children??<span className="text-sm text-slate-500">筛选控件将在后续任务接入</span>}</div>}
export function DataTableShell({children}:{children:ReactNode}){return <div className="overflow-hidden rounded-lg border bg-white dark:bg-slate-950">{children}</div>}
export function SkeletonTable(){return <div className="space-y-px">{[1,2,3,4,5].map(i=><div key={i} className="h-14 animate-pulse bg-slate-100 dark:bg-slate-900"/>)}</div>}
