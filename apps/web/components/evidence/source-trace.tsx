"use client";

import type { SourceProvenance } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/context";

export function SourceTrace({source}:{source:SourceProvenance}) {
  const {t,enumLabel}=useI18n();
  // Defense in depth for external editorial URLs as well as API-generated YouTube links.
  const url=source.source_url && /^https?:\/\//i.test(source.source_url) ? source.source_url : null;
  return <div className="space-y-2 text-sm">
    {source.evidence_role&&source.evidence_role!=="unknown"&&<p className="text-xs font-medium">{enumLabel(source.evidence_role)}</p>}
    {url ? <a href={url} target="_blank" rel="noopener noreferrer" className="font-medium text-cyan-700 underline decoration-cyan-700/30 underline-offset-4 dark:text-cyan-400">{source.video_title||t("evidence.openSource")} ↗</a> : <><p className="text-amber-700 dark:text-amber-400">{t("evidence.unavailable")}</p>{source.video_title&&<p>{source.video_title}</p>}</>}
    {source.channel_name&&<p className="text-slate-500">{t("signals.channel")}: {source.channel_name}</p>}
    {source.source_comment_id&&<p className="text-xs text-slate-500">{t("evidence.parentVideo")}</p>}
    {source.source_comment_text&&<details className="rounded border p-3"><summary className="cursor-pointer text-xs font-medium">{t("evidence.rawComment")}</summary><blockquote className="mt-2 whitespace-pre-wrap break-words leading-6">{source.source_comment_text}</blockquote></details>}
    {url&&<p className="text-xs text-slate-500">{t("evidence.sourceHint")}</p>}
  </div>;
}
