"use client";

import { useState } from "react";
import { Bookmark, BookmarkMinus } from "lucide-react";
import { ApiClient, ApiError } from "@/lib/api/client";
import { createClient } from "@/lib/auth/client";

export function WatchlistButton({opportunityId,initialWatchlisted,onChange}:{opportunityId:string;initialWatchlisted:boolean;onChange?:(watchlisted:boolean)=>void}){
  const [watchlisted,setWatchlisted]=useState(initialWatchlisted);const [loading,setLoading]=useState(false);const [message,setMessage]=useState("");
  const toggle=async()=>{if(loading)return;setLoading(true);setMessage("");try{const {data:{session}}=await createClient().auth.getSession();if(!session){setMessage("登录状态已失效");return}const api=new ApiClient(async()=>session.access_token);const result=watchlisted?await api.removeFromWatchlist(opportunityId):await api.addToWatchlist(opportunityId);setWatchlisted(result.watchlisted);setMessage(result.watchlisted?"已加入关注列表":"已从关注列表移除");onChange?.(result.watchlisted)}catch(reason){const error=reason instanceof ApiError?reason:new ApiError(0,"关注列表操作失败");setMessage(`${error.status===403?"没有操作权限":error.status===404?"机会不可用":error.message}${error.requestId?` · ${error.requestId}`:""}`)}finally{setLoading(false)}};
  const label=loading?"正在更新关注列表":watchlisted?"从关注列表移除":"加入关注列表";
  return <div aria-label={watchlisted?"已关注":undefined} className="inline-flex flex-col items-start gap-1">{watchlisted&&<span className="sr-only">已关注</span>}<button type="button" aria-label={label} aria-pressed={watchlisted} disabled={loading} onClick={()=>void toggle()} className="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium disabled:opacity-50">{watchlisted?<BookmarkMinus size={14}/>:<Bookmark size={14}/>}<span>{loading?"更新中…":watchlisted?"已关注 · 移除":"加入关注"}</span></button>{message&&<span role="status" className="max-w-48 text-[11px] text-slate-500">{message}</span>}</div>
}
