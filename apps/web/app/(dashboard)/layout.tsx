import { redirect } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { ApiClient } from "@/lib/api/client";
import { createClient } from "@/lib/auth/server";
export default async function DashboardLayout({children}:{children:React.ReactNode}){const supabase=await createClient();if(!supabase)redirect("/login");const [{data:{user:identity}},{data:{session}}]=await Promise.all([supabase.auth.getUser(),supabase.auth.getSession()]);if(!identity||!session)redirect("/login");let user;try{user=await new ApiClient(async()=>session.access_token).getCurrentUser()}catch{redirect("/login")}return <AppShell user={user}>{children}</AppShell>}
