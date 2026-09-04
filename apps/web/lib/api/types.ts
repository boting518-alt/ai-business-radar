export type AppRole = "user" | "admin";
export interface CurrentUser { auth_user_id:string; user_profile_id:string; role:AppRole; email:string|null }
export type MarketStage = "unknown"|"emerging"|"accelerating"|"validated"|"crowded"|"mature"|"declining";
export interface TrendItem { window_type:string;period_start:string;period_end:string;aggregation_version:string;video_count:number;new_video_count:number;unique_channel_count:number;total_views:number;comment_count:number;pain_signal_count:number;demand_signal_count:number;purchase_intent_signal_count:number;revenue_signal_count:number;competitor_signal_count:number;momentum_score:string|null }
export interface EvidenceSummary { active_signal_count:number;distinct_video_count:number;distinct_channel_count:number;pain_signal_count:number;demand_signal_count:number;purchase_intent_signal_count:number;revenue_signal_count:number }
export interface RadarOpportunity { id:string;slug:string;name:string;one_line_thesis:string|null;industry:string|null;sub_industry:string|null;customer_type:string|null;business_model:string|null;market_stage:MarketStage;competition_level:string|null;build_difficulty:string|null;sales_difficulty:string|null;opportunity_score:string|null;confidence_score:string|null;hype_risk_score:string|null;trend:TrendItem|null;first_detected_at:string;last_activity_at:string;evidence_summary:EvidenceSummary;watchlisted:boolean }
export interface RadarResponse { items:RadarOpportunity[];total:number;offset:number;limit:number }
export type QueryValue = string | number | boolean | readonly (string | number | boolean)[] | undefined | null;
export type Query = Record<string, QueryValue>;
export interface ReviewDecision { decision:"approve"|"merge"|"create_new"|"reject"|"ignore"|"defer";merge_target_opportunity_id?:string|null;decision_notes?:string|null }
