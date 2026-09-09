"use client";

import { useState } from "react";
import type { EvidenceItem } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/context";
import { EmptyState } from "@/components/states/states";
import { SourceTrace } from "./source-trace";

export function EvidenceList({items,emptyMessage}:{items:EvidenceItem[];emptyMessage:string}) {
  if (!items.length) return <EmptyState title={emptyMessage} description=""/>;
  return <ul className="space-y-3">{items.map(item=><EvidenceCard key={`${item.evidence_kind}:${item.evidence_id}`} item={item}/>)}</ul>;
}

function EvidenceCard({item}:{item:EvidenceItem}) {
  const {locale,t,enumLabel}=useI18n();
  const [original,setOriginal]=useState(false);
  const translated=item.statement_localized||item.evidence_localized;
  return <li className="space-y-3 rounded-lg border p-4">
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <span className="rounded bg-slate-100 px-2 py-1 dark:bg-slate-800">{enumLabel(item.signal_type||item.evidence_type)}</span>
      <span>{item.claim_status?enumLabel(item.claim_status):t("evidence.unknownClaim")}</span>
      {item.relationship_type&&<span className="rounded border px-2 py-1">{enumLabel(item.relationship_type)}</span>}
      {item.evidence_kind!=="linked_signal"&&<span>{t("evidence.explicit")}</span>}
      <span className="text-slate-500">{enumLabel(item.source_type)}</span>
      {item.observed_at&&<time dateTime={item.observed_at} className="text-slate-500">{new Intl.DateTimeFormat(locale,{dateStyle:"medium"}).format(new Date(item.observed_at))}</time>}
    </div>
    <p className="font-medium leading-6">{item.statement}</p>
    {item.evidence_text&&<div className="border-l-2 border-cyan-600 pl-3"><p className="text-xs text-slate-500">{item.evidence_localized?t("signals.translatedEvidence"):t("signals.evidence")}</p><p className="mt-1 whitespace-pre-wrap text-sm leading-6">{item.evidence_text}</p></div>}
    {translated&&<><button type="button" aria-expanded={original} onClick={()=>setOriginal(!original)} className="text-xs font-medium text-cyan-700 hover:underline">{original?t("signals.hideOriginal"):t("signals.original")}</button>{original&&<div className="space-y-2 rounded bg-slate-50 p-3 dark:bg-slate-900"><p className="text-xs text-slate-500">{t("evidence.canonical")}</p><p className="text-sm">{item.original_statement}</p>{item.original_evidence_text&&<p className="whitespace-pre-wrap text-sm">{item.original_evidence_text}</p>}</div>}</>}
    {item.localization_stale&&<p className="text-xs text-amber-700">{t("evidence.stale")}</p>}
    {item.signal_id&&<p className="text-xs text-slate-500">{t("evidence.canonicalHint")}</p>}
    <SourceTrace source={item}/>
  </li>;
}
