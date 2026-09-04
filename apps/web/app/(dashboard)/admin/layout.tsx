import { notFound, redirect } from "next/navigation";
import { ApiClient } from "@/lib/api/client";
import { createClient } from "@/lib/auth/server";
export default async function AdminLayout({children}:{children:React.ReactNode}){const supabase=await createClient();if(!supabase)redirect("/login");const [{data:{user:identity}},{data:{session}}]=await Promise.all([supabase.auth.getUser(),supabase.auth.getSession()]);if(!identity||!session)redirect("/login");const user=await new ApiClient(async()=>session.access_token).getCurrentUser();if(user.role!=="admin")notFound();return children}
