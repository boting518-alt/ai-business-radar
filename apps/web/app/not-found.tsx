import Link from "next/link";
import { EmptyState } from "@/components/states/states";
export default function NotFound(){return <main className="mx-auto max-w-xl p-10"><EmptyState title="未找到该机会" description="它可能不存在，或当前账户不可见。"/><Link href="/opportunities" className="mt-4 inline-block underline">返回机会库</Link></main>}
