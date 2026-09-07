"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Search, X } from "lucide-react";
import { ApiClient, ApiError } from "@/lib/api/client";
import { createClient } from "@/lib/auth/client";
import type { MarketStage, Query, RadarOpportunity, RadarResponse } from "@/lib/api/types";
import { EmptyState, ErrorState } from "@/components/states/states";
import { DataTableShell, PageHeader, ScoreBadge, SkeletonTable, StageBadge, StatCard } from "@/components/ui/primitives";
import { WatchlistButton } from "@/components/watchlist/watchlist-button";
import { useI18n } from "@/lib/i18n/context";

const WINDOWS=["7d","30d","90d"] as const;
const STAGES:MarketStage[]=["unknown","emerging","accelerating","validated","crowded","mature","declining"];
const SORTS=[["score","Score"],["momentum","Momentum"],["confidence","Confidence"],["hype","Hype Risk"],["recent","Recent"]] as const;
const FILTER_KEYS=["q","industry","business_model","customer_type","market_stage","score_min","confidence_min","hype_max"] as const;
const DEFAULT_LIMIT=25;

function numeric(value:string|null){return value===null?null:Number(value)}
function metric(value:string|null){const number=numeric(value);return number===null?"—":number.toFixed(Number.isInteger(number)?0:1)}
function percentage(value:string|null){const formatted=metric(value);return formatted==="—"?formatted:`${formatted}%`}
function shortDate(value:string){return new Intl.DateTimeFormat("zh-CN",{year:"numeric",month:"short",day:"numeric"}).format(new Date(value))}

export function RadarDashboard(){
  const {locale}=useI18n();
  const router=useRouter();
  const searchParams=useSearchParams();
  const serialized=searchParams.toString();
  const params=useMemo(()=>new URLSearchParams(serialized),[serialized]);
  const requestedWindow=params.get("window_type");
  const windowType=WINDOWS.includes(requestedWindow as typeof WINDOWS[number])?requestedWindow!:"7d";
  const requestedSort=params.get("sort");
  const sort=SORTS.some(([value])=>value===requestedSort)?requestedSort!:"score";
  const direction=params.get("direction")==="asc"?"asc":"desc";
  const offset=Math.max(0,Number(params.get("offset"))||0);
  const requestedLimit=Number(params.get("limit"));
  const limit=Number.isInteger(requestedLimit)&&requestedLimit>=1&&requestedLimit<=100?requestedLimit:DEFAULT_LIMIT;
  const [data,setData]=useState<RadarResponse|null>(null);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState<ApiError|null>(null);
  const [refreshKey,setRefreshKey]=useState(0);
  const [fetchedAt,setFetchedAt]=useState<Date|null>(null);

  const replace=useCallback((updates:Record<string,string|null>,resetOffset=true)=>{
    const next=new URLSearchParams(serialized);
    Object.entries(updates).forEach(([key,value])=>value?next.set(key,value):next.delete(key));
    if(resetOffset)next.delete("offset");
    const query=next.toString();
    router.replace(query?`/radar?${query}`:"/radar");
  },[router,serialized]);

  useEffect(()=>{
    let active=true;
    async function load(){
      setLoading(true);setError(null);
      try{
        const {data:{session}}=await createClient().auth.getSession();
        if(!session){router.replace("/login");return}
        const query:Query={window_type:windowType,sort,direction,offset,limit,locale};
        FILTER_KEYS.forEach(key=>{const value=params.get(key);if(value)query[key]=value});
        const result=await new ApiClient(async()=>session.access_token).getRadar(query);
        if(active){setData(result);setFetchedAt(new Date())}
      }catch(reason){
        if(reason instanceof ApiError&&reason.status===401){router.replace("/login");return}
        if(active)setError(reason instanceof ApiError?reason:new ApiError(0,"无法加载 Radar 数据"));
      }finally{if(active)setLoading(false)}
    }
    void load();return()=>{active=false};
  },[direction,limit,locale,offset,params,refreshKey,router,sort,windowType]);

  const hasFilters=FILTER_KEYS.some(key=>params.has(key));
  const page=Math.floor(offset/limit)+1;
  const pageCount=data?Math.max(1,Math.ceil(data.total/data.limit)):1;
  const scores=data?.items.map(item=>numeric(item.opportunity_score)).filter((value):value is number=>value!==null)??[];
  const confidences=data?.items.map(item=>numeric(item.confidence_score)).filter((value):value is number=>value!==null)??[];
  const average=(values:number[])=>values.length?(values.reduce((sum,value)=>sum+value,0)/values.length).toFixed(1):"—";
  const clearFilters=()=>{const next=new URLSearchParams(serialized);FILTER_KEYS.forEach(key=>next.delete(key));next.delete("offset");router.replace(next.toString()?`/radar?${next}`:"/radar")};
  const submitFilters=(event:FormEvent<HTMLFormElement>)=>{event.preventDefault();const form=new FormData(event.currentTarget);const updates:Record<string,string|null>={};FILTER_KEYS.forEach(key=>updates[key]=String(form.get(key)??"").trim()||null);replace(updates)};
  const changeSort=(nextSort:string)=>replace({sort:nextSort,direction:nextSort===sort?(direction==="desc"?"asc":"desc"):"desc"});

  return <div className="space-y-5">
    <PageHeader title="AI 商业机会雷达" description="按证据、趋势动量和商业信号排序的新兴 AI 商业机会。" actions={fetchedAt?<span className="hidden text-xs text-slate-500 sm:block">本页查询于 {fetchedAt.toLocaleTimeString("zh-CN",{hour:"2-digit",minute:"2-digit"})}</span>:undefined}/>
    <section aria-label="当前结果摘要" className="grid grid-cols-2 gap-3 lg:grid-cols-4"><StatCard label="当前页机会" value={data?String(data.items.length):"—"}/><StatCard label="当前页平均 Opportunity Score" value={data?average(scores):"—"}/><StatCard label="当前页平均 Confidence" value={data&&confidences.length?`${average(confidences)}%`:"—"}/><StatCard label="符合条件总数" value={data?String(data.total):"—"}/></section>
    <div className="flex flex-wrap items-center justify-between gap-3 border-y py-3"><div className="flex rounded-lg bg-slate-100 p-1 dark:bg-slate-900" aria-label="趋势时间窗口">{WINDOWS.map(value=><button key={value} type="button" aria-pressed={windowType===value} onClick={()=>replace({window_type:value})} className={`rounded-md px-4 py-2 text-sm font-semibold uppercase focus-visible:outline-2 ${windowType===value?"bg-slate-950 text-white shadow-sm dark:bg-white dark:text-slate-950":"text-slate-500 hover:text-slate-950 dark:hover:text-white"}`}>{value}</button>)}</div><p className="text-xs text-slate-500">摘要仅代表当前返回页</p></div>
    <form key={serialized} aria-label="Radar 筛选" onSubmit={submitFilters} className="rounded-xl border bg-white p-3 shadow-sm dark:bg-slate-950"><div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      <label className="xl:col-span-2"><span className="mb-1 block text-xs font-medium text-slate-500">搜索</span><span className="flex items-center gap-2 rounded-md border px-3"><Search size={15} className="text-slate-400"/><input name="q" defaultValue={params.get("q")??""} placeholder="名称、论点或行业" className="h-10 min-w-0 flex-1 bg-transparent text-sm outline-none"/></span></label>
      <TextFilter name="industry" label="行业 Industry" value={params.get("industry")}/><TextFilter name="business_model" label="商业模式 Business Model" value={params.get("business_model")}/><TextFilter name="customer_type" label="客户 Customer" value={params.get("customer_type")}/>
      <label><span className="mb-1 block text-xs font-medium text-slate-500">市场阶段 Market Stage</span><select name="market_stage" defaultValue={params.get("market_stage")??""} className="h-9 w-full rounded-md border bg-transparent px-3 text-sm"><option value="">全部阶段</option>{STAGES.map(stage=><option key={stage}>{stage}</option>)}</select></label>
      <NumberFilter name="score_min" label="最低机会评分" value={params.get("score_min")}/><NumberFilter name="confidence_min" label="最低置信度" value={params.get("confidence_min")}/><NumberFilter name="hype_max" label="最高炒作风险" value={params.get("hype_max")}/>
      <div className="flex items-end gap-2 xl:col-span-3"><button className="h-9 rounded-md bg-slate-950 px-4 text-sm font-medium text-white dark:bg-white dark:text-slate-950">应用筛选</button>{hasFilters&&<button type="button" onClick={clearFilters} className="flex h-9 items-center gap-1 rounded-md border px-3 text-sm"><X size={14}/>清除筛选</button>}</div>
    </div></form>
    <div className="flex items-center justify-between gap-3"><h2 className="font-semibold">机会排行</h2><label className="flex items-center gap-2 text-xs text-slate-500">排序<select aria-label="排序方式" value={sort} onChange={event=>changeSort(event.target.value)} className="h-9 rounded-md border bg-transparent px-2 text-sm text-slate-900 dark:text-white">{SORTS.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select><button type="button" aria-label={`按${direction==="desc"?"升序":"降序"}排列`} onClick={()=>replace({direction:direction==="desc"?"asc":"desc"})} className="rounded-md border p-2">{direction==="desc"?<ArrowDown size={15}/>:<ArrowUp size={15}/>}</button></label></div>
    {loading?<DataTableShell><SkeletonTable/></DataTableShell>:error?<ErrorState message={error.status===403?"你没有查看 Radar 的权限":error.message} requestId={error.requestId??undefined} onRetry={()=>setRefreshKey(value=>value+1)}/>:data&&data.items.length===0?<EmptyState title={hasFilters?"没有符合筛选条件的机会":"目前还没有可见的已评分机会"} description={hasFilters?"调整或清除筛选条件后重试。":"机会经审核激活并完成评分后，会显示在这里。"} action={hasFilters?<button onClick={clearFilters} className="mt-4 rounded-md border px-4 py-2 text-sm">清除筛选</button>:undefined}/>:data&&<RadarResults items={data.items} sort={sort} direction={direction} onSort={changeSort}/>}
    {!loading&&!error&&data&&data.items.length>0&&<nav aria-label="分页" className="flex items-center justify-between border-t pt-4"><p className="text-sm text-slate-500">第 {page} / {pageCount} 页 · 共 {data.total} 项</p><div className="flex gap-2"><button type="button" disabled={offset===0} onClick={()=>replace({offset:String(Math.max(0,offset-limit))},false)} className="flex items-center gap-1 rounded-md border px-3 py-2 text-sm disabled:opacity-40"><ChevronLeft size={15}/>上一页</button><button type="button" disabled={offset+data.limit>=data.total} onClick={()=>replace({offset:String(offset+limit)},false)} className="flex items-center gap-1 rounded-md border px-3 py-2 text-sm disabled:opacity-40">下一页<ChevronRight size={15}/></button></div></nav>}
  </div>
}

function TextFilter({name,label,value}:{name:string;label:string;value:string|null}){return <label><span className="mb-1 block text-xs font-medium text-slate-500">{label}</span><input name={name} defaultValue={value??""} className="h-9 w-full rounded-md border bg-transparent px-3 text-sm"/></label>}
function NumberFilter({name,label,value}:{name:string;label:string;value:string|null}){return <label><span className="mb-1 block text-xs font-medium text-slate-500">{label}</span><input name={name} type="number" min="0" max="100" step="1" defaultValue={value??""} className="h-9 w-full rounded-md border bg-transparent px-3 text-sm tabular-nums"/></label>}

function RadarResults({items,sort,direction,onSort}:{items:RadarOpportunity[];sort:string;direction:string;onSort:(sort:string)=>void}){return <DataTableShell><table className="hidden w-full table-fixed text-left text-sm lg:table"><thead className="border-b bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:bg-slate-900"><tr><th scope="col" className="w-[30%] px-4 py-3">Opportunity</th><th scope="col" className="w-[10%] px-3 py-3">Industry</th><th scope="col" className="w-[9%] px-3 py-3">Stage</th><Sortable label="Score" active={sort==="score"} direction={direction} onClick={()=>onSort("score")}/><Sortable label="Confidence" active={sort==="confidence"} direction={direction} onClick={()=>onSort("confidence")}/><Sortable label="Hype Risk" active={sort==="hype"} direction={direction} onClick={()=>onSort("hype")}/><Sortable label="Momentum" active={sort==="momentum"} direction={direction} onClick={()=>onSort("momentum")}/><th scope="col" className="w-[12%] px-3 py-3">Evidence</th><Sortable label="Last activity" active={sort==="recent"} direction={direction} onClick={()=>onSort("recent")}/></tr></thead><tbody className="divide-y">{items.map(item=><RadarRow key={item.id} item={item}/>)}</tbody></table><div className="divide-y lg:hidden">{items.map(item=><RadarCard key={item.id} item={item}/>)}</div></DataTableShell>}
function Sortable({label,active,direction,onClick}:{label:string;active:boolean;direction:string;onClick:()=>void}){return <th scope="col" className="px-2 py-3"><button type="button" onClick={onClick} className="inline-flex items-center gap-1 text-left hover:text-slate-950 dark:hover:text-white">{label}{active&&(direction==="desc"?<ArrowDown size={12}/>:<ArrowUp size={12}/>)}</button></th>}
function RadarRow({item}:{item:RadarOpportunity}){const evidence=item.evidence_summary;return <tr className="align-top hover:bg-slate-50/70 dark:hover:bg-slate-900/60"><td className="px-4 py-4"><div className="min-w-0"><Link href={`/opportunities/${item.slug||item.id}`} className="font-semibold hover:underline">{item.name}</Link>{item.one_line_thesis&&<p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{item.one_line_thesis}</p>}{item.customer_type&&<p className="mt-1 text-[11px] text-slate-400">{item.customer_type}</p>}<div className="mt-2"><WatchlistButton opportunityId={item.id} initialWatchlisted={item.watchlisted}/></div></div></td><td className="px-3 py-4 text-xs text-slate-600 dark:text-slate-300">{item.industry??"—"}</td><td className="px-3 py-4"><StageBadge stage={item.market_stage}/></td><td className="px-2 py-4"><ScoreBadge label="" value={numeric(item.opportunity_score)}/></td><MetricCell title="Evidence confidence" value={item.confidence_score}/><MetricCell title="Attention relative to commercial evidence" value={item.hype_risk_score}/><MetricCell title="Recent trend activity" value={item.trend?.momentum_score??null}/><td className="px-3 py-4 text-xs leading-5 text-slate-500"><span className="block">{evidence.active_signal_count} signals</span><span>{evidence.distinct_video_count} videos · {evidence.distinct_channel_count} channels</span></td><td className="px-2 py-4 text-xs text-slate-500">{shortDate(item.last_activity_at)}</td></tr>}
function MetricCell({value,title}:{value:string|null;title:string}){return <td className="px-2 py-4 font-medium tabular-nums" title={title}>{title==="Evidence confidence"?percentage(value):metric(value)}</td>}
function RadarCard({item}:{item:RadarOpportunity}){const evidence=item.evidence_summary;return <article className="p-4"><div className="flex items-start justify-between gap-3"><div><Link href={`/opportunities/${item.slug||item.id}`} className="font-semibold hover:underline">{item.name}</Link><div className="mt-2 flex flex-wrap items-center gap-2"><StageBadge stage={item.market_stage}/><WatchlistButton opportunityId={item.id} initialWatchlisted={item.watchlisted}/></div></div><ScoreBadge label="Score" value={numeric(item.opportunity_score)}/></div>{item.one_line_thesis&&<p className="mt-3 text-sm leading-6 text-slate-500">{item.one_line_thesis}</p>}<dl className="mt-4 grid grid-cols-3 gap-2 border-y py-3"><CardMetric label="Momentum" value={item.trend?.momentum_score??null}/><CardMetric label="Confidence" value={item.confidence_score} percentage/><CardMetric label="Hype Risk" value={item.hype_risk_score}/></dl><p className="mt-3 text-xs text-slate-500">{evidence.active_signal_count} signals · {evidence.distinct_video_count} videos · {evidence.distinct_channel_count} channels</p></article>}
function CardMetric({label,value,percentage:asPercentage=false}:{label:string;value:string|null;percentage?:boolean}){return <div><dt className="text-[11px] text-slate-500">{label}</dt><dd className="mt-1 font-semibold tabular-nums">{asPercentage?percentage(value):metric(value)}</dd></div>}
