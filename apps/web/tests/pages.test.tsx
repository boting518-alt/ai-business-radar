import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Radar from "@/app/(dashboard)/radar/page";
import Opportunities from "@/app/(dashboard)/opportunities/page";
import Signals from "@/app/(dashboard)/signals/page";
import Watchlist from "@/app/(dashboard)/watchlist/page";
import Reviews from "@/app/(dashboard)/admin/review/page";
describe("MVP route shells",()=>{it.each([[Radar,"Radar"],[Opportunities,"机会库"],[Signals,"信号"],[Watchlist,"关注列表"],[Reviews,"人工审核"]] as const)("renders its page heading",(Page,title)=>{render(<Page/>);expect(screen.getByRole("heading",{name:title})).toBeInTheDocument()})});
