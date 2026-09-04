import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { config } from "@/lib/config";

export async function createClient() {
  if (!config.supabaseUrl || !config.supabaseAnonKey) return null;
  const store = await cookies();
  return createServerClient(config.supabaseUrl, config.supabaseAnonKey, {
    cookies: { getAll: () => store.getAll(), setAll: (items) => { try { items.forEach(({name,value,options}) => store.set(name,value,options)); } catch {} } },
  });
}
