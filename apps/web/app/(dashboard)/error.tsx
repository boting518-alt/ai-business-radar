"use client";
import { ErrorState } from "@/components/states/states";
export default function Error({error,reset}:{error:Error&{digest?:string};reset:()=>void}){return <ErrorState message="页面加载失败" requestId={error.digest} onRetry={reset}/>}
