"use client";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { createClient } from "@/lib/auth/client";
export function LogoutButton(){const router=useRouter();return <Button onClick={async()=>{await createClient().auth.signOut();router.replace("/login");router.refresh()}} className="bg-transparent text-slate-600 hover:bg-slate-100 dark:text-slate-300">退出</Button>}
