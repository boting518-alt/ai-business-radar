import { createBrowserClient } from "@supabase/ssr";
import { config } from "@/lib/config";

export function createClient() {
  if (!config.supabaseUrl || !config.supabaseAnonKey) throw new Error("Supabase is not configured");
  return createBrowserClient(config.supabaseUrl, config.supabaseAnonKey);
}
