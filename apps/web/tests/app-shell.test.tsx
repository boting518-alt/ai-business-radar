import { render, screen } from "@testing-library/react";
import { vi, describe, expect, it } from "vitest";
vi.mock("next/navigation",()=>({useRouter:()=>({replace:vi.fn(),refresh:vi.fn()})}));
vi.mock("@/lib/auth/client",()=>({createClient:()=>({auth:{signOut:vi.fn()}})}));
import { AppShell } from "@/components/layout/app-shell";

const base={auth_user_id:"a",user_profile_id:"u",email:"analyst@example.com"};
describe("AppShell",()=>{it("renders required user navigation without admin review",()=>{render(<AppShell user={{...base,role:"user"}}>content</AppShell>);expect(screen.getByRole("link",{name:"Radar"})).toBeInTheDocument();expect(screen.getByRole("link",{name:"机会"})).toBeInTheDocument();expect(screen.getByRole("link",{name:"信号"})).toBeInTheDocument();expect(screen.getByRole("link",{name:"关注"})).toBeInTheDocument();expect(screen.queryByRole("link",{name:"人工审核"})).not.toBeInTheDocument();expect(screen.queryByText("管理员 Admin")).not.toBeInTheDocument();expect(screen.getByRole("button",{name:"退出"})).toBeInTheDocument()});it("shows a separated review workspace and badge for backend-resolved admin",()=>{render(<AppShell user={{...base,role:"admin"}}>content</AppShell>);expect(screen.getByRole("link",{name:"人工审核"})).toBeInTheDocument();expect(screen.getByText("审核工作区 Review")).toBeInTheDocument();expect(screen.getByText("管理员 Admin")).toBeInTheDocument()})});
