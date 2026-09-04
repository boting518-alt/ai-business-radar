import { redirect } from "next/navigation";
import { createClient } from "@/lib/auth/server";
export default async function Home(){const client=await createClient();const {data}=client?await client.auth.getUser():{data:{user:null}};redirect(data.user?"/radar":"/login")}
