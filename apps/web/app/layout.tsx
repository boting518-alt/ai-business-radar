import type { Metadata } from "next";
import "./globals.css";
import { LocaleProvider } from "@/lib/i18n/context";
export const metadata:Metadata={title:"AI Business Radar",description:"YouTube-derived AI business intelligence"};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="zh-CN"><body><LocaleProvider>{children}</LocaleProvider></body></html>}
