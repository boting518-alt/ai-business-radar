import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OpportunityDossier } from "@/components/opportunities/opportunity-dossier";
import type { EvidenceItem, OpportunityDetail, ScoreItem, TrendItem } from "@/lib/api/types";

const replace=vi.fn();
const router={replace};
let query="";
vi.mock("next/navigation",()=>({useRouter:()=>router,useSearchParams:()=>new URLSearchParams(query)}));
vi.mock("@/lib/auth/client",()=>({createClient:()=>({auth:{getSession:vi.fn().mockResolvedValue({data:{session:{access_token:"token"}}})}})}));

function trend(window_type="7d",momentum_score:string|null="68.4"):TrendItem{return {window_type,period_start:"2026-08-28T00:00:00Z",period_end:"2026-09-04T00:00:00Z",aggregation_version:"trend-v001",video_count:7,new_video_count:4,unique_channel_count:4,total_views:120000,comment_count:40,pain_signal_count:5,demand_signal_count:3,purchase_intent_signal_count:2,revenue_signal_count:1,competitor_signal_count:2,momentum_score}}
const score:ScoreItem={calculated_at:"2026-09-04T00:00:00Z",scoring_version:"score-v001",trend_velocity_score:"68.4",demand_evidence_score:"81",revenue_evidence_score:"62",pain_severity_score:"75",competition_white_space_score:"70",build_feasibility_score:"60",distribution_ease_score:"72",opportunity_score:"74.3",confidence_score:"78",hype_risk_score:"29"};
const detail:OpportunityDetail={opportunity:{id:"opp-1",slug:"ai-dental-receptionist",name:"AI Dental Receptionist",one_line_thesis:"Automates inbound scheduling for dental practices.",industry:"Healthcare",sub_industry:"Dental",customer_type:"SMB",problem:"Missed calls become lost appointments.",solution:"An AI receptionist answers and schedules.",business_model:"SaaS",primary_technology:"Voice AI",typical_price_min:"199",typical_price_max:"499",typical_price_currency:"USD",typical_price_period:"month",competition_level:"medium",build_difficulty:"medium",sales_difficulty:"low",market_stage:"accelerating",first_detected_at:"2026-08-01T00:00:00Z",last_activity_at:"2026-09-04T00:00:00Z"},current_intelligence:score,trend_summary:{"7d":trend("7d"),"30d":trend("30d","61"),"90d":trend("90d","55")},evidence_summary:{active_signal_count:12,distinct_video_count:7,distinct_channel_count:4,pain_signal_count:5,demand_signal_count:3,purchase_intent_signal_count:2,revenue_signal_count:1},watchlisted:true};
const scores=[score,{...score,calculated_at:"2026-08-28T00:00:00Z",opportunity_score:"71"}];
const trends=[trend(),{...trend(),period_end:"2026-08-28T00:00:00Z",momentum_score:"63"}];
const evidence:Array<EvidenceItem&{comment_author?:string}> = Array.from({length:10},(_,index)=>({evidence_id:`ev-${index}`,evidence_type:index?"demand":"pain",summary:index?`Evidence ${index}`:"Customers miss calls after hours.",source_type:"youtube_video",observed_at:"2026-09-03T00:00:00Z",strength:"0.8",confidence:"0.9",youtube_video_id:"video-1",video_title:"AI receptionist case study",comment_author:"private-author"}));

function response(body:unknown,status=200,requestId?:string){return Promise.resolve(new Response(JSON.stringify(body),{status,headers:{"Content-Type":"application/json",...(requestId?{"X-Request-ID":requestId}:{})}}))}
function mockApi(options:{detail?:unknown;trends?:unknown;scores?:unknown;evidence?:unknown;status?:number;requestId?:string}={}){
  vi.stubGlobal("fetch",vi.fn().mockImplementation((input:RequestInfo|URL)=>{const url=String(input);if(options.status)return response(options.detail??{detail:"Failed"},options.status,options.requestId);if(url.includes("/trends"))return response(options.trends??trends);if(url.includes("/scores"))return response(options.scores??scores);if(url.includes("/evidence"))return response(options.evidence??evidence);return response(options.detail??detail)}));
}

describe("Opportunity detail page",()=>{
  beforeEach(()=>{query="";replace.mockReset();mockApi()});

  it("loads a slug through four parallel product APIs",async()=>{
    render(<OpportunityDossier identifier="ai-dental-receptionist"/>);
    expect(screen.getByLabelText("正在加载机会详情")).toBeInTheDocument();
    expect(await screen.findByRole("heading",{name:"AI Dental Receptionist"})).toBeInTheDocument();
    await waitFor(()=>expect(fetch).toHaveBeenCalledTimes(4));
    const urls=vi.mocked(fetch).mock.calls.map(call=>String(call[0]));
    expect(urls.some(url=>url.endsWith("/opportunities/ai-dental-receptionist"))).toBe(true);
    expect(urls.some(url=>url.includes("/trends?window_type=7d"))).toBe(true);
    expect(urls.some(url=>url.includes("/scores?limit=50"))).toBe(true);
    expect(urls.some(url=>url.includes("/evidence?offset=0&limit=10"))).toBe(true);
  });

  it("renders persisted identity, metrics, business fields, price, and watchlist",async()=>{
    render(<OpportunityDossier identifier="ai-dental-receptionist"/>);await screen.findByRole("heading",{name:"AI Dental Receptionist"});
    expect(screen.getByText(detail.opportunity.one_line_thesis!)).toBeInTheDocument();
    expect(screen.getAllByText("74.3").length).toBeGreaterThan(0);expect(screen.getAllByText("78").length).toBeGreaterThan(0);expect(screen.getAllByText("29").length).toBeGreaterThan(0);expect(screen.getAllByText("68.4").length).toBeGreaterThan(0);
    expect(screen.getAllByText("accelerating").length).toBeGreaterThan(0);expect(screen.getByText(detail.opportunity.problem!)).toBeInTheDocument();expect(screen.getByText("199–499 USD / month")).toBeInTheDocument();expect(screen.getByText("已关注")).toBeInTheDocument();
  });

  it("renders all persisted score components without exposing inputs",async()=>{
    mockApi({detail:{...detail,current_intelligence:{...score,inputs_snapshot:"do-not-render"}}});render(<OpportunityDossier identifier="opp-1"/>);await screen.findByText("Score breakdown");
    for(const label of ["Trend Velocity","Demand Evidence","Revenue Evidence","Pain Severity","Competition White Space","Build Feasibility","Distribution Ease"])expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.queryByText("do-not-render")).not.toBeInTheDocument();
  });

  it("shows all three trend summaries and trend history",async()=>{
    render(<OpportunityDossier identifier="opp-1"/>);await screen.findByText("Trend overview");
    expect(screen.getAllByRole("heading",{level:3})).toHaveLength(3);expect(screen.getByText("Trend history")).toBeInTheDocument();expect(screen.getAllByText("63").length).toBeGreaterThan(0);
  });

  it("writes trend window changes to the URL",async()=>{
    render(<OpportunityDossier identifier="opp-1"/>);await screen.findByText("Trend history");fireEvent.click(screen.getByRole("button",{name:"30d"}));expect(replace).toHaveBeenCalledWith("/opportunities/opp-1?trend_window=30d");
  });

  it("renders score history and evidence safely",async()=>{
    render(<OpportunityDossier identifier="opp-1"/>);await screen.findByText("Supporting evidence");expect(screen.getByText("Customers miss calls after hours.")).toBeInTheDocument();expect(screen.getAllByText("AI receptionist case study",{exact:false}).length).toBeGreaterThan(0);expect(screen.getByText("Score history")).toBeInTheDocument();expect(screen.getAllByText("71").length).toBeGreaterThan(0);expect(screen.queryByText("private-author")).not.toBeInTheDocument();
  });

  it("paginates bounded evidence through URL state",async()=>{
    render(<OpportunityDossier identifier="opp-1"/>);await screen.findByText("Supporting evidence");fireEvent.click(screen.getByRole("button",{name:/下一页/}));expect(replace).toHaveBeenCalledWith("/opportunities/opp-1?evidence_offset=10");
  });

  it("keeps missing data absent or marked safely",async()=>{
    mockApi({detail:{...detail,opportunity:{...detail.opportunity,problem:null,typical_price_min:null,typical_price_max:null},current_intelligence:null,trend_summary:{"7d":null,"30d":null,"90d":null}},trends:[],scores:[],evidence:[]});render(<OpportunityDossier identifier="opp-1"/>);await screen.findByRole("heading",{name:"AI Dental Receptionist"});expect(screen.queryByText("Missed calls become lost appointments.")).not.toBeInTheDocument();expect(screen.getAllByText("—").length).toBeGreaterThan(0);expect(screen.getAllByText("No trend data yet.")).toHaveLength(3);expect(screen.getByText("Trend history is not available yet.")).toBeInTheDocument();expect(screen.getByText("No supporting evidence is available yet.")).toBeInTheDocument();
  });

  it("shows a safe 404 and Radar navigation",async()=>{
    mockApi({status:404,detail:{detail:"Opportunity was not found"}});render(<OpportunityDossier identifier="hidden"/>);expect(await screen.findByText("Opportunity not found or unavailable.")).toBeInTheDocument();expect(screen.getByRole("link",{name:"返回 Radar"})).toHaveAttribute("href","/radar");expect(screen.queryByText("hidden status")).not.toBeInTheDocument();
  });

  it("shows request ID for server errors and redirects 401",async()=>{
    mockApi({status:500,detail:{error:{message:"Detail unavailable"}},requestId:"req-detail"});const first=render(<OpportunityDossier identifier="opp-1"/>);expect(await screen.findByRole("alert")).toHaveTextContent("req-detail");first.unmount();replace.mockClear();mockApi({status:401,detail:{detail:"Unauthorized"}});render(<OpportunityDossier identifier="opp-1"/>);await waitFor(()=>expect(replace).toHaveBeenCalledWith("/login"));
  });
});
