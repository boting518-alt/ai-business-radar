import { readFileSync } from "node:fs";
import { globSync } from "node:fs";
import { describe, expect, it } from "vitest";
describe("browser source security",()=>{it("does not reference server secrets",()=>{const forbidden=["SUPABASE_SERVICE_ROLE_KEY","DATABASE_URL","OPENAI_API_KEY","YOUTUBE_API_KEY","REDIS_URL","SUPABASE_JWT_SECRET"];const files=globSync("{app,components,lib}/**/*.{ts,tsx}");const source=files.map(file=>readFileSync(file,"utf8")).join("\n");for(const secret of forbidden)expect(source).not.toContain(secret)})});
