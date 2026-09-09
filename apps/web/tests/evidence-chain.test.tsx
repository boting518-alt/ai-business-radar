import {fireEvent,render,screen} from "@testing-library/react";
import {describe,it,expect} from "vitest";
import {EvidenceList} from "@/components/evidence/evidence-list";
import {SourceTrace} from "@/components/evidence/source-trace";
import {LocaleProvider,useI18n} from "@/lib/i18n/context";
import type {EvidenceItem} from "@/lib/api/types";

const item:EvidenceItem={evidence_id:"ev1",evidence_kind:"linked_signal",signal_id:"s1",signal_type:"pricing",evidence_type:"pricing",statement:"评论者说明价格为 508 美元。",summary:"评论者说明价格为 508 美元。",evidence_text:"含运费 508 美元",original_statement:"Commenter states the price is $508.",original_evidence_text:"$508 including shipping",claim_status:"unknown",relationship_type:"contradicting",source_type:"comment",observed_at:"2026-09-09T00:00:00Z",strength:"0.7",confidence:"0.8",source_video_id:"v1",youtube_video_id:"9_cH8DVQ7Zs",video_title:"Micro Duck video",source_comment_id:"c1",youtube_comment_id:"stored-comment",source_comment_text:"Ordered it! $508 shipped.",source_url:"https://www.youtube.com/watch?v=9_cH8DVQ7Zs",source_navigation:"parent_video",statement_localized:true,evidence_localized:true,localization_stale:false};
function Language(){const {setLocale}=useI18n();return <button onClick={()=>setLocale("en-US")}>English</button>}

describe("Evidence provenance UI",()=>{
  it("distinguishes translated intelligence, canonical English, and original comment",()=>{
    render(<EvidenceList items={[item]} emptyMessage="empty"/>);
    expect(screen.getByText("反对")).toBeInTheDocument();expect(screen.getByText("未知")).toBeInTheDocument();
    expect(screen.getByText("定价")).toBeInTheDocument();expect(screen.getByText(item.statement)).toBeInTheDocument();
    expect(screen.queryByText(item.original_statement)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button",{name:"查看原文"}));
    expect(screen.getByText(item.original_statement)).toBeInTheDocument();expect(screen.getByText(item.original_evidence_text!)).toBeInTheDocument();
    expect(screen.getByText("英文规范文本（提取结果）")).toBeInTheDocument();
    expect(screen.getByText("来源评论原文")).toBeInTheDocument();expect(screen.getByText(item.source_comment_text!)).toBeInTheDocument();
    expect(screen.getByText("评论来源于该视频")).toBeInTheDocument();
    const link=screen.getByRole("link",{name:/Micro Duck video/});
    expect(link).toHaveAttribute("href",item.source_url);expect(link).toHaveAttribute("target","_blank");expect(link).toHaveAttribute("rel","noopener noreferrer");
  });
  it("retains evidence when provenance cannot be navigated and rejects unsafe links",()=>{
    render(<EvidenceList items={[{...item,source_url:null,source_navigation:"unavailable"}]} emptyMessage="empty"/>);
    expect(screen.getByText(item.statement)).toBeInTheDocument();expect(screen.getByText("来源链接暂不可用，已保留证据文本")).toBeInTheDocument();expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
  it("does not render an executable source URL",()=>{render(<SourceTrace source={{source_url:"javascript:alert(1)"}}/>);expect(screen.queryByRole("link")).not.toBeInTheDocument()});
  it("renders English labels and a true empty state",()=>{
    const view=render(<LocaleProvider><Language/><EvidenceList items={[item]} emptyMessage="No related evidence yet"/></LocaleProvider>);
    fireEvent.click(screen.getByRole("button",{name:"English"}));
    expect(screen.getByText("Contradicting")).toBeInTheDocument();expect(screen.getByText("Comment from this video")).toBeInTheDocument();
    view.rerender(<LocaleProvider><EvidenceList items={[]} emptyMessage="No related evidence yet"/></LocaleProvider>);
    expect(screen.getByText("No related evidence yet")).toBeInTheDocument();
    window.localStorage.clear();
  });
});
