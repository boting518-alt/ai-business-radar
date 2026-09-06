import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RadarDashboard } from "@/components/radar/radar-dashboard";
import type { RadarOpportunity, RadarResponse } from "@/lib/api/types";

const replace=vi.fn();
let query="";
vi.mock("next/navigation",()=>({useRouter:()=>({replace}),useSearchParams:()=>new URLSearchParams(query)}));
vi.mock("@/lib/auth/client",()=>({createClient:()=>({auth:{getSession:vi.fn().mockResolvedValue({data:{session:{access_token:"token"}}})}})}));

const item:RadarOpportunity={
  id:"00000000-0000-0000-0000-000000000001",slug:"ai-dental-receptionist",name:"AI Dental Receptionist",one_line_thesis:"Automates inbound scheduling for independent dental practices.",industry:"Healthcare",sub_industry:"Dental",customer_type:"SMB",business_model:"SaaS",market_stage:"accelerating",competition_level:"medium",build_difficulty:"medium",sales_difficulty:"medium",opportunity_score:"82.50",confidence_score:"74.00",hype_risk_score:"31.00",trend:{window_type:"7d",period_start:"2026-08-28T00:00:00Z",period_end:"2026-09-04T00:00:00Z",aggregation_version:"trend-v001",video_count:7,new_video_count:4,unique_channel_count:4,total_views:120000,comment_count:40,pain_signal_count:5,demand_signal_count:3,purchase_intent_signal_count:2,revenue_signal_count:1,competitor_signal_count:2,momentum_score:"68.40"},first_detected_at:"2026-08-01T00:00:00Z",last_activity_at:"2026-09-04T00:00:00Z",evidence_summary:{active_signal_count:12,distinct_video_count:7,distinct_channel_count:4,pain_signal_count:5,demand_signal_count:3,purchase_intent_signal_count:2,revenue_signal_count:1},watchlisted:true,
};
const response:RadarResponse={items:[item,{...item,id:"2",slug:"workflow",name:"AI Workflow Auditor",opportunity_score:null,trend:null,watchlisted:false}],total:27,offset:0,limit:25};

describe("Radar page",()=>{
  beforeEach(()=>{query="";replace.mockReset();vi.stubGlobal("fetch",vi.fn().mockImplementation(()=>Promise.resolve(new Response(JSON.stringify(response),{status:200,headers:{"Content-Type":"application/json"}}))))});

  it("loads and displays persisted Radar intelligence",async()=>{
    render(<RadarDashboard/>);
    expect(screen.getByText("机会排行")).toBeInTheDocument();
    expect(document.querySelector(".animate-pulse")).toBeInTheDocument();
    expect(await screen.findAllByText("AI Dental Receptionist")).toHaveLength(2);
    expect(screen.getAllByText("82.5").length).toBeGreaterThan(0);
    expect(screen.getAllByText("74%").length).toBeGreaterThan(0);
    expect(screen.getAllByText("31").length).toBeGreaterThan(0);
    expect(screen.getAllByText("68.4").length).toBeGreaterThan(0);
    expect(screen.getAllByText("accelerating").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/12 signals/).length).toBeGreaterThan(0);
    expect(screen.getAllByLabelText("已关注").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link",{name:"AI Dental Receptionist"})[0]).toHaveAttribute("href","/opportunities/ai-dental-receptionist");
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("defaults to 7D and sends the default backend query",async()=>{
    render(<RadarDashboard/>);
    expect(screen.getByRole("button",{name:"7d"})).toHaveAttribute("aria-pressed","true");
    await waitFor(()=>expect(fetch).toHaveBeenCalled());
    expect(String(vi.mocked(fetch).mock.calls[0][0])).toContain("window_type=7d");expect(String(vi.mocked(fetch).mock.calls[0][0])).toContain("sort=score");expect(String(vi.mocked(fetch).mock.calls[0][0])).toContain("limit=25");
  });

  it.each([["30d","/radar?window_type=30d"],["90d","/radar?window_type=90d"]])("writes the %s window to URL",async(window,url)=>{
    render(<RadarDashboard/>);await userEvent.click(screen.getByRole("button",{name:window}));expect(replace).toHaveBeenCalledWith(url);
  });

  it("submits supported filters and resets pagination",async()=>{
    query="offset=25";render(<RadarDashboard/>);
    await userEvent.type(screen.getByLabelText("搜索"),"agents");
    await userEvent.type(screen.getByLabelText("行业 Industry"),"Healthcare");
    await userEvent.selectOptions(screen.getByLabelText("市场阶段 Market Stage"),"accelerating");
    await userEvent.type(screen.getByLabelText("最低机会评分"),"70");
    await userEvent.type(screen.getByLabelText("最低置信度"),"60");
    await userEvent.type(screen.getByLabelText("最高炒作风险"),"40");
    await userEvent.click(screen.getByRole("button",{name:"应用筛选"}));
    const url=replace.mock.calls.at(-1)?.[0] as string;
    expect(url).toContain("q=agents");expect(url).toContain("industry=Healthcare");expect(url).toContain("market_stage=accelerating");expect(url).toContain("score_min=70");expect(url).toContain("confidence_min=60");expect(url).toContain("hype_max=40");expect(url).not.toContain("offset");
  });

  it.each([["Momentum","momentum"],["Score","score"]])("requests backend %s sorting",async(label,value)=>{
    render(<RadarDashboard/>);await screen.findAllByText("AI Dental Receptionist");fireEvent.change(screen.getByLabelText("排序方式"),{target:{value}});expect(replace).toHaveBeenLastCalledWith(expect.stringContaining(`sort=${value}`));
  });

  it("moves through offset pagination",async()=>{
    const first=render(<RadarDashboard/>);await screen.findAllByText("AI Dental Receptionist");fireEvent.click(screen.getByRole("button",{name:/下一页/}));expect(replace).toHaveBeenLastCalledWith("/radar?offset=25");
    first.unmount();query="offset=25";replace.mockClear();render(<RadarDashboard/>);await screen.findAllByText("AI Dental Receptionist");fireEvent.click(screen.getByRole("button",{name:/上一页/}));expect(replace).toHaveBeenLastCalledWith("/radar?offset=0");
  });

  it.each([["","目前还没有可见的已评分机会"],["industry=Unknown","没有符合筛选条件的机会"]])("renders the correct empty state for %s",async(params,title)=>{
    query=params;vi.stubGlobal("fetch",vi.fn().mockImplementation(()=>Promise.resolve(new Response(JSON.stringify({items:[],total:0,offset:0,limit:25}),{status:200,headers:{"Content-Type":"application/json"}}))));render(<RadarDashboard/>);expect(await screen.findByText(title)).toBeInTheDocument();
  });

  it("shows safe API error details and retry",async()=>{
    vi.stubGlobal("fetch",vi.fn().mockImplementation(()=>Promise.resolve(new Response(JSON.stringify({error:{message:"Radar 暂时不可用",code:"server_error"}}),{status:500,headers:{"Content-Type":"application/json","X-Request-ID":"req-radar"}}))));render(<RadarDashboard/>);expect(await screen.findByRole("alert")).toHaveTextContent("Radar 暂时不可用");expect(screen.getByRole("alert")).toHaveTextContent("req-radar");expect(screen.getByRole("button",{name:"重试"})).toBeInTheDocument();
  });

  it("redirects an unauthenticated API response",async()=>{
    vi.stubGlobal("fetch",vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:"Unauthorized"}),{status:401,headers:{"Content-Type":"application/json"}})));render(<RadarDashboard/>);await waitFor(()=>expect(replace).toHaveBeenCalledWith("/login"));
  });
});
