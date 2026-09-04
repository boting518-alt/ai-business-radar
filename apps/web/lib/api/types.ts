export type AppRole = "user" | "admin";
export interface CurrentUser { auth_user_id:string; user_profile_id:string; role:AppRole; email:string|null }
export interface RadarResponse { items: Array<{id:string;slug:string;name:string;opportunity_score:string|null;confidence_score:string|null;hype_risk_score:string|null;watchlisted:boolean}>;total:number;offset:number;limit:number }
export type Query = Record<string, string | number | boolean | undefined | null>;
export interface ReviewDecision { decision:"approve"|"merge"|"create_new"|"reject"|"ignore"|"defer";merge_target_opportunity_id?:string|null;decision_notes?:string|null }
