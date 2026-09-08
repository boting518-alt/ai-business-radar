import { config } from "@/lib/config";
import type { CurrentUser, DiscoveryRun, DiscoveryRunPage, DiscoverySystemStatus, DiscoveryTopic, EvidenceItem, OpportunityDetail, OpportunityLibraryResponse, Query, RadarResponse, ReviewDecision, ReviewListResult, ReviewTask, ReviewWorkflowResult, ScoreItem, SignalFeedItem, TrendItem, WatchlistMembershipResult, WatchlistResult } from "./types";

export class ApiError extends Error {
  constructor(public status:number, message:string, public code="http_error", public requestId:string|null=null, public details?:unknown) { super(message); this.name="ApiError"; }
}

export class ApiClient {
  constructor(private getToken:()=>Promise<string|null>, private baseUrl=config.apiBaseUrl) {}
  async request<T>(path:string, init:RequestInit={}) {
    const token=await this.getToken();
    const headers=new Headers(init.headers); headers.set("Accept","application/json");
    if (init.body) headers.set("Content-Type","application/json");
    if (token) headers.set("Authorization",`Bearer ${token}`);
    const response=await fetch(`${this.baseUrl}${path}`,{...init,headers,cache:"no-store"});
    const requestId=response.headers.get("X-Request-ID");
    const data=await response.json().catch(()=>null);
    if (!response.ok) throw new ApiError(response.status,data?.error?.message ?? data?.detail ?? "Request failed",data?.error?.code,requestId,data);
    return data as T;
  }
  private path(path:string,query:Query={}) { const p=new URLSearchParams(); Object.entries(query).forEach(([k,v])=>{if(v==null)return;if(Array.isArray(v))v.forEach(item=>p.append(k,String(item)));else p.set(k,String(v))}); const s=p.toString(); return s?`${path}?${s}`:path; }
  getCurrentUser=()=>this.request<CurrentUser>("/api/v1/auth/me");
  getRadar=(query:Query={})=>this.request<RadarResponse>(this.path("/api/v1/radar",query));
  listOpportunities=(query:Query={})=>this.request<OpportunityLibraryResponse>(this.path("/api/v1/opportunities",query));
  getOpportunity=(id:string,query:Query={})=>this.request<OpportunityDetail>(this.path(`/api/v1/opportunities/${encodeURIComponent(id)}`,query));
  getOpportunityTrends=(id:string,query:Query={})=>this.request<TrendItem[]>(this.path(`/api/v1/opportunities/${encodeURIComponent(id)}/trends`,query));
  getOpportunityScores=(id:string,query:Query={})=>this.request<ScoreItem[]>(this.path(`/api/v1/opportunities/${encodeURIComponent(id)}/scores`,query));
  getOpportunityEvidence=(id:string,query:Query={})=>this.request<EvidenceItem[]>(this.path(`/api/v1/opportunities/${encodeURIComponent(id)}/evidence`,query));
  listSignals=(query:Query={})=>this.request<SignalFeedItem[]>(this.path("/api/v1/signals",query));
  getWatchlist=()=>this.request<WatchlistResult>("/api/v1/watchlist");
  addToWatchlist=(id:string)=>this.request<WatchlistMembershipResult>(`/api/v1/watchlist/items/${encodeURIComponent(id)}`,{method:"POST"});
  removeFromWatchlist=(id:string)=>this.request<WatchlistMembershipResult>(`/api/v1/watchlist/items/${encodeURIComponent(id)}`,{method:"DELETE"});
  listReviews=(query:Query={})=>this.request<ReviewListResult>(this.path("/api/v1/admin/reviews",query));
  getReview=(id:string)=>this.request<ReviewTask>(`/api/v1/admin/reviews/${encodeURIComponent(id)}`);
  claimReview=(id:string)=>this.request<ReviewWorkflowResult>(`/api/v1/admin/reviews/${encodeURIComponent(id)}/claim`,{method:"POST"});
  decideReview=(id:string,body:ReviewDecision)=>this.request<ReviewWorkflowResult>(`/api/v1/admin/reviews/${encodeURIComponent(id)}/decision`,{method:"POST",body:JSON.stringify(body)});
  listDiscoveryTopics=()=>this.request<DiscoveryTopic[]>("/api/v1/admin/discovery/topics");
  createDiscoveryTopic=(body:unknown)=>this.request<DiscoveryTopic>("/api/v1/admin/discovery/topics",{method:"POST",body:JSON.stringify(body)});
  runDiscoveryTopic=(id:string)=>this.request<DiscoveryRun[]>(`/api/v1/admin/discovery/topics/${id}/run`,{method:"POST"});
  pauseDiscoveryTopic=(id:string)=>this.request<DiscoveryTopic>(`/api/v1/admin/discovery/topics/${id}/pause`,{method:"POST"});
  resumeDiscoveryTopic=(id:string)=>this.request<DiscoveryTopic>(`/api/v1/admin/discovery/topics/${id}/resume`,{method:"POST"});
  duplicateDiscoveryTopic=(id:string)=>this.request<DiscoveryTopic>(`/api/v1/admin/discovery/topics/${id}/duplicate`,{method:"POST"});
  getDiscoveryStatus=()=>this.request<DiscoverySystemStatus>("/api/v1/admin/discovery/system-status");
  listDiscoveryRuns=(query:Query={})=>this.request<DiscoveryRunPage>(this.path("/api/v1/admin/discovery/runs",query));
}
