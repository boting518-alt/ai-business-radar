"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { ApiClient, ApiError } from "@/lib/api/client";
import { createClient } from "@/lib/auth/client";
import type { EvidenceItem, OpportunityDetail, ScoreItem, TrendItem } from "@/lib/api/types";
import { EmptyState, ErrorState } from "@/components/states/states";
import { StageBadge } from "@/components/ui/primitives";
import { WatchlistButton } from "@/components/watchlist/watchlist-button";

const WINDOWS=["7d","30d","90d"] as const;
const EVIDENCE_LIMIT=10;
const SCORE_COMPONENTS=[
  ["trend_velocity_score","Trend Velocity"],["demand_evidence_score","Demand Evidence"],["revenue_evidence_score","Revenue Evidence"],["pain_severity_score","Pain Severity"],["competition_white_space_score","Competition White Space"],["build_feasibility_score","Build Feasibility"],["distribution_ease_score","Distribution Ease"],
] as const;

function display(value:string|null|undefined){if(value==null)return "—";const number=Number(value);return Number.isFinite(number)?number.toFixed(Number.isInteger(number)?0:1):value}
function percentage(value:string|null|undefined){const formatted=display(value);return formatted==="—"?formatted:`${formatted}%`}
function date(value:string|null|undefined){return value?new Intl.DateTimeFormat("zh-CN",{year:"numeric",month:"short",day:"numeric"}).format(new Date(value)):"—"}
function price(detail:OpportunityDetail["opportunity"]){
  const {typical_price_min:min,typical_price_max:max,typical_price_currency:currency,typical_price_period:period}=detail;
  if(min==null&&max==null)return null;
  const amount=min!=null&&max!=null?`${display(min)}–${display(max)}`:display(min??max);
  return [amount,currency,period?`/ ${period}`:null].filter(Boolean).join(" ");
}

export function OpportunityDossier({identifier}:{identifier:string}){
  const router=useRouter();
  const searchParams=useSearchParams();
  const serialized=searchParams.toString();
  const params=useMemo(()=>new URLSearchParams(serialized),[serialized]);
  const requestedWindow=params.get("trend_window");
  const trendWindow:typeof WINDOWS[number]=WINDOWS.includes(requestedWindow as typeof WINDOWS[number])?requestedWindow as typeof WINDOWS[number]:"7d";
  const evidenceOffset=Math.max(0,Number(params.get("evidence_offset"))||0);
  const [detail,setDetail]=useState<OpportunityDetail|null>(null);
  const [trends,setTrends]=useState<TrendItem[]>([]);
  const [scores,setScores]=useState<ScoreItem[]>([]);
  const [evidence,setEvidence]=useState<EvidenceItem[]>([]);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState<ApiError|null>(null);
  const [retry,setRetry]=useState(0);

  const updateUrl=useCallback((updates:Record<string,string|null>)=>{
    const next=new URLSearchParams(serialized);
    Object.entries(updates).forEach(([key,value])=>value&&value!=="0"?next.set(key,value):next.delete(key));
    const query=next.toString();router.replace(query?`/opportunities/${encodeURIComponent(identifier)}?${query}`:`/opportunities/${encodeURIComponent(identifier)}`);
  },[identifier,router,serialized]);

  useEffect(()=>{
    let active=true;
    async function load(){
      setLoading(true);setError(null);
      try{
        const {data:{session}}=await createClient().auth.getSession();
        if(!session){router.replace("/login");return}
        const api=new ApiClient(async()=>session.access_token);
        const [nextDetail,nextTrends,nextScores,nextEvidence]=await Promise.all([
          api.getOpportunity(identifier),api.getOpportunityTrends(identifier,{window_type:trendWindow,limit:50}),api.getOpportunityScores(identifier,{limit:50}),api.getOpportunityEvidence(identifier,{offset:evidenceOffset,limit:EVIDENCE_LIMIT}),
        ]);
        if(active){setDetail(nextDetail);setTrends(nextTrends);setScores(nextScores);setEvidence(nextEvidence)}
      }catch(reason){
        if(reason instanceof ApiError&&reason.status===401){router.replace("/login");return}
        if(active)setError(reason instanceof ApiError?reason:new ApiError(0,"无法加载机会详情"));
      }finally{if(active)setLoading(false)}
    }
    void load();return()=>{active=false};
  },[evidenceOffset,identifier,retry,router,trendWindow]);

  if(loading)return <DossierSkeleton/>;
  if(error)return <div className="space-y-4"><BackLink/>{error.status===404?<EmptyState title="Opportunity not found or unavailable." description="该机会不存在，或当前不可查看。" action={<Link href="/radar" className="mt-4 inline-block rounded-md border px-4 py-2 text-sm">返回 Radar</Link>}/>:<ErrorState message={error.status===403?"你没有查看该机会的权限":error.message} requestId={error.requestId??undefined} onRetry={()=>setRetry(value=>value+1)}/>}</div>;
  if(!detail)return null;

  const opportunity=detail.opportunity;
  const current=detail.current_intelligence;
  const currentTrend=detail.trend_summary[trendWindow];
  const formattedPrice=price(opportunity);
  const businessFields=[
    ["Customer",opportunity.customer_type],["Problem",opportunity.problem],["Solution",opportunity.solution],["Business Model",opportunity.business_model],["Primary Technology",opportunity.primary_technology],["Typical Price Range",formattedPrice],["Competition Level",opportunity.competition_level],["Build Difficulty",opportunity.build_difficulty],["Sales Difficulty",opportunity.sales_difficulty],["Market Stage",opportunity.market_stage],
  ].filter((entry):entry is [string,string]=>entry[1]!=null&&entry[1]!=="");

  return <article className="space-y-7">
    <nav aria-label="面包屑" className="flex items-center gap-2 text-sm text-slate-500"><Link href="/radar" className="hover:text-slate-950 hover:underline dark:hover:text-white">Radar</Link><span aria-hidden="true">/</span><span className="truncate text-slate-900 dark:text-slate-100">{opportunity.name}</span></nav>
    <header className="border-b pb-6"><div className="flex flex-wrap items-start justify-between gap-4"><div className="max-w-4xl"><div className="flex flex-wrap items-center gap-2"><h1 className="text-3xl font-semibold tracking-tight">{opportunity.name}</h1><StageBadge stage={opportunity.market_stage}/><WatchlistButton opportunityId={opportunity.id} initialWatchlisted={detail.watchlisted}/></div>{opportunity.one_line_thesis&&<p className="mt-3 text-base leading-7 text-slate-600 dark:text-slate-300">{opportunity.one_line_thesis}</p>}<div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">{[opportunity.industry,opportunity.sub_industry,opportunity.customer_type,opportunity.business_model].filter(Boolean).map(value=><span key={value}>{value}</span>)}</div></div><div className="text-right text-xs text-slate-500"><p>首次发现 {date(opportunity.first_detected_at)}</p><p className="mt-1">最近活动 {date(opportunity.last_activity_at)}</p></div></div></header>
    <section aria-labelledby="key-metrics"><h2 id="key-metrics" className="sr-only">关键情报指标</h2><div className="grid grid-cols-2 divide-x divide-y rounded-xl border bg-white sm:grid-cols-4 sm:divide-y-0 dark:bg-slate-950"><PrimaryMetric label="机会评分 Opportunity Score" value={current?.opportunity_score} definition="综合商业机会强度"/><PrimaryMetric label="置信度 Confidence" value={current?.confidence_score} definition="支持证据的强度与覆盖度" percentage/><PrimaryMetric label="炒作风险 Hype Risk" value={current?.hype_risk_score} definition="关注度相对于商业证据的风险"/><PrimaryMetric label="趋势动量 Momentum" value={currentTrend?.momentum_score} definition="近期趋势活跃度"/></div></section>
    <Section title="Business thesis"><dl className="grid gap-px overflow-hidden rounded-lg border bg-slate-200 md:grid-cols-2 dark:bg-slate-800">{businessFields.map(([label,value])=><div key={label} className="bg-white p-4 dark:bg-slate-950"><dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt><dd className="mt-2 text-sm leading-6">{value}</dd></div>)}</dl></Section>
    <Section title="Trend overview"><div className="grid gap-3 lg:grid-cols-3">{WINDOWS.map(window=><TrendSummary key={window} window={window} trend={detail.trend_summary[window]}/>)}</div></Section>
    <Section title="Score breakdown">{current?<div className="divide-y rounded-lg border">{SCORE_COMPONENTS.map(([key,label])=><div key={key} className="grid grid-cols-[minmax(10rem,1fr)_3fr_3rem] items-center gap-3 px-4 py-3"><span className="text-sm">{label}</span><progress aria-label={label} max="100" value={Number(current[key])} className="h-2 w-full accent-slate-800"/><span className="text-right text-sm font-semibold tabular-nums">{display(current[key])}</span></div>)}</div>:<EmptyState title="评分尚不可用" description="该机会还没有持久化评分。"/>}</Section>
    <Section title="Evidence summary"><div className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border bg-slate-200 sm:grid-cols-4 lg:grid-cols-7 dark:bg-slate-800">{[["Signals",detail.evidence_summary.active_signal_count],["Videos",detail.evidence_summary.distinct_video_count],["Channels",detail.evidence_summary.distinct_channel_count],["Pain",detail.evidence_summary.pain_signal_count],["Demand",detail.evidence_summary.demand_signal_count],["Purchase Intent",detail.evidence_summary.purchase_intent_signal_count],["Revenue",detail.evidence_summary.revenue_signal_count]].map(([label,value])=><div key={label} className="bg-white p-3 dark:bg-slate-950"><p className="text-[11px] text-slate-500">{label}</p><p className="mt-1 text-xl font-semibold tabular-nums">{value}</p></div>)}</div></Section>
    <Section title="Supporting evidence"><EvidenceList items={evidence}/><div className="mt-3 flex justify-end gap-2"><button type="button" disabled={evidenceOffset===0} onClick={()=>updateUrl({evidence_offset:String(Math.max(0,evidenceOffset-EVIDENCE_LIMIT))})} className="flex items-center gap-1 rounded-md border px-3 py-2 text-sm disabled:opacity-40"><ChevronLeft size={15}/>上一页</button><button type="button" disabled={evidence.length<EVIDENCE_LIMIT} onClick={()=>updateUrl({evidence_offset:String(evidenceOffset+EVIDENCE_LIMIT)})} className="flex items-center gap-1 rounded-md border px-3 py-2 text-sm disabled:opacity-40">下一页<ChevronRight size={15}/></button></div></Section>
    <Section title="Trend history" actions={<WindowSelector selected={trendWindow} onChange={window=>updateUrl({trend_window:window})}/>}>{trends.length?<HistoryTable headings={["Period end","Momentum","Videos","Channels","Pain","Demand"]} rows={trends.map(trend=>[date(trend.period_end),display(trend.momentum_score),trend.video_count,trend.unique_channel_count,trend.pain_signal_count,trend.demand_signal_count])}/>:<EmptyState title="Trend history is not available yet." description="所选窗口还没有历史趋势记录。"/>}</Section>
    <Section title="Score history">{scores.length>1?<HistoryTable headings={["Calculated","Opportunity Score","Confidence","Hype Risk"]} rows={scores.map(score=>[date(score.calculated_at),display(score.opportunity_score),display(score.confidence_score),display(score.hype_risk_score)])}/>:<EmptyState title="Current score available; historical scoring has not accumulated yet." description={scores.length?`当前评分日期：${date(scores[0].calculated_at)}`:"该机会还没有评分历史。"}/>}</Section>
    <footer className="flex flex-wrap justify-between gap-2 border-t pt-4 text-xs text-slate-500"><span>Opportunity ID: {opportunity.id}</span><span>Scoring version: {current?.scoring_version??"—"}</span></footer>
  </article>
}

function BackLink(){return <Link href="/radar" className="text-sm text-slate-500 hover:underline">← 返回 Radar</Link>}
function DossierSkeleton(){return <div aria-label="正在加载机会详情" className="space-y-5">{["h-5 w-48","h-28","h-24","h-64","h-48"].map((style,index)=><div key={index} className={`${style} animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800`}/>)}</div>}
function Section({title,actions,children}:{title:string;actions?:React.ReactNode;children:React.ReactNode}){return <section aria-labelledby={`section-${title.replaceAll(" ","-").toLowerCase()}`} className="space-y-3"><div className="flex items-center justify-between gap-3"><h2 id={`section-${title.replaceAll(" ","-").toLowerCase()}`} className="text-sm font-semibold uppercase tracking-wider text-slate-500">{title}</h2>{actions}</div>{children}</section>}
function PrimaryMetric({label,value,definition,percentage:asPercentage=false}:{label:string;value:string|null|undefined;definition:string;percentage?:boolean}){return <div className="p-4" title={definition}><p className="text-xs text-slate-500">{label}</p><p className="mt-2 text-3xl font-semibold tabular-nums">{asPercentage?percentage(value):display(value)}</p><p className="mt-1 text-[11px] text-slate-400">{definition}</p></div>}
function TrendSummary({window,trend}:{window:string;trend:TrendItem|null}){if(!trend)return <div className="rounded-lg border border-dashed p-4"><h3 className="font-semibold uppercase">{window}</h3><p className="mt-4 text-sm text-slate-500">No trend data yet.</p></div>;const metrics=[["Momentum",display(trend.momentum_score)],["Videos",trend.video_count],["New videos",trend.new_video_count],["Channels",trend.unique_channel_count],["Comments",trend.comment_count],["Pain",trend.pain_signal_count],["Demand",trend.demand_signal_count],["Purchase intent",trend.purchase_intent_signal_count],["Revenue",trend.revenue_signal_count]];return <div className="rounded-lg border p-4"><h3 className="font-semibold uppercase">{window}</h3><dl className="mt-4 grid grid-cols-3 gap-3">{metrics.map(([label,value])=><div key={label}><dt className="text-[10px] uppercase text-slate-500">{label}</dt><dd className="mt-1 text-sm font-semibold tabular-nums">{value}</dd></div>)}</dl></div>}
function WindowSelector({selected,onChange}:{selected:string;onChange:(value:string)=>void}){return <div className="flex rounded-md bg-slate-100 p-1 dark:bg-slate-900" aria-label="趋势历史窗口">{WINDOWS.map(window=><button key={window} type="button" aria-pressed={selected===window} onClick={()=>onChange(window)} className={`rounded px-3 py-1 text-xs font-semibold uppercase ${selected===window?"bg-white shadow-sm dark:bg-slate-700":"text-slate-500"}`}>{window}</button>)}</div>}
function EvidenceList({items}:{items:EvidenceItem[]}){if(!items.length)return <EmptyState title="No supporting evidence is available yet." description="该机会目前没有可展示的支持证据。"/>;return <ul className="divide-y rounded-lg border">{items.map(item=><li key={item.evidence_id} className="p-4"><div className="flex flex-wrap items-center gap-2 text-xs"><span className="rounded bg-slate-100 px-2 py-1 dark:bg-slate-800">{item.evidence_type}</span><span className="text-slate-500">{item.source_type}</span>{item.observed_at&&<time className="text-slate-400">{date(item.observed_at)}</time>}</div><p className="mt-3 text-sm leading-6">{item.summary}</p><div className="mt-2 flex flex-wrap gap-4 text-xs text-slate-500">{item.video_title&&<span>Video: {item.video_title}</span>}<span>Strength {display(item.strength)}</span><span>Confidence {display(item.confidence)}</span></div></li>)}</ul>}
function HistoryTable({headings,rows}:{headings:string[];rows:Array<Array<string|number>>}){return <div className="overflow-x-auto rounded-lg border"><table className="w-full min-w-[36rem] text-left text-sm"><thead className="border-b bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-900"><tr>{headings.map(heading=><th key={heading} scope="col" className="px-4 py-3">{heading}</th>)}</tr></thead><tbody className="divide-y">{rows.map((row,index)=><tr key={index}>{row.map((value,column)=><td key={column} className="px-4 py-3 tabular-nums">{value}</td>)}</tr>)}</tbody></table></div>}
