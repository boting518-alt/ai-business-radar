import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiClient, ApiError } from "@/lib/api/client";

afterEach(()=>vi.unstubAllGlobals());
describe("ApiClient",()=>{
  it("attaches bearer token and parses Radar data",async()=>{const fetcher=vi.fn().mockResolvedValue(new Response(JSON.stringify({items:[],total:0,offset:0,limit:25}),{status:200,headers:{"X-Request-ID":"req-1","Content-Type":"application/json"}}));vi.stubGlobal("fetch",fetcher);const result=await new ApiClient(async()=>"access-token","http://api").getRadar();expect(result.total).toBe(0);expect(fetcher.mock.calls[0][1].headers.get("Authorization")).toBe("Bearer access-token")});
  it.each([401,403])("normalizes HTTP %s and captures request ID",async(status)=>{vi.stubGlobal("fetch",vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:"Denied"}),{status,headers:{"X-Request-ID":"req-denied"}})));const promise=new ApiClient(async()=>null,"http://api").getCurrentUser();await expect(promise).rejects.toMatchObject({status,requestId:"req-denied",message:"Denied"} satisfies Partial<ApiError>)});
});
