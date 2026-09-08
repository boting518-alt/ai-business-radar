import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DiscoveryConsole } from "@/components/discovery/discovery-console";

vi.mock("@/lib/auth/client", () => ({
  createClient: () => ({
    auth: { getSession: async () => ({ data: { session: { access_token: "token" } } }) },
  }),
}));

const run = {
  id: "run-1", topic_id: "topic-1", topic_run_id: "batch-1", query_id: "query-1",
  query_text: "AI dental receptionist", trigger_type: "manual", status: "queued",
  started_at: null, completed_at: null, videos_discovered: 0, quota_estimate: 0,
  error_code: null, error_message_safe: null, worker_message_id: "message-1",
};
const batch = {
  id: "batch-1", topic_id: "topic-1", trigger_type: "manual", status: "queued",
  requested_query_count: 2, queued_query_count: 2, queued: 2, running: 0,
  completed: 0, partial: 0, failed: 0, terminal_count: 0, quota_estimate: 0,
  started_at: "2026-09-08T00:00:00Z", completed_at: null,
  runs: [run, { ...run, id: "run-2", query_id: "query-2" }],
};
const topic = {
  id: "topic-1", name: "AI Dental Front Desk", description: "Dental research",
  status: "paused", default_schedule: "manual", default_max_videos: 5,
  default_max_pages: 1, default_max_comments_per_video: 10, query_count: 2,
  last_run_at: null, next_run_at: null, latest_run: null, current_topic_run: null,
};
const json = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
}));

function mockFetch(runResponse: unknown = batch) {
  vi.stubGlobal("fetch", vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("system-status")) return json({ redis: "configured", worker: "unknown", scheduler: "configured", youtube_api: "configured", openai_api: "configured" });
    if (url.includes("/topic-runs/batch-1")) return json({ ...batch, status: "completed", queued: 0, completed: 2, terminal_count: 2, completed_at: "2026-09-08T00:01:00Z", runs: batch.runs.map(item => ({ ...item, status: "completed" })) });
    if (url.includes("/topics/topic-1/run")) return json(runResponse, runResponse === batch ? 202 : 409);
    return json([topic]);
  }));
}

afterEach(() => vi.useRealTimers());

describe("Discovery Console", () => {
  it("polls only the current batch and stops at terminal", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let release: (value: Response) => void = () => {};
    mockFetch();
    const original = vi.mocked(fetch).getMockImplementation()!;
    vi.mocked(fetch).mockImplementation((input, init) => String(input).includes("/topics/topic-1/run")
      ? new Promise(resolve => { release = resolve; }) : original(input, init));
    render(<DiscoveryConsole />);
    await screen.findByText("AI Dental Front Desk");
    const runButton = screen.getByRole("button", { name: "Run Now" });
    expect(runButton).toHaveClass("cursor-pointer");
    await userEvent.click(runButton);
    expect(screen.getByRole("button", { name: "排队中…" })).toBeDisabled();
    release(await json(batch, 202));
    expect(await screen.findByText("发现批次已排队（2/2）。")).toBeInTheDocument();
    await screen.findByRole("button", { name: "Queued…" });
    await act(async () => vi.advanceTimersByTime(3000));
    await screen.findByText("发现批次已结束：completed（2/2）");
    const calls = vi.mocked(fetch).mock.calls.map(([url]) => String(url));
    expect(calls.some(url => url.includes("/topic-runs/batch-1"))).toBe(true);
    expect(calls.some(url => url.includes("/discovery/runs?"))).toBe(false);
    const count = calls.length;
    await act(async () => vi.advanceTimersByTime(6000));
    expect(vi.mocked(fetch).mock.calls).toHaveLength(count);
  });

  it("renders duplicate batch conflict as domain status", async () => {
    mockFetch({ error: { message: "Discovery topic already queued or running" } });
    render(<DiscoveryConsole />);
    await screen.findByText("AI Dental Front Desk");
    await userEvent.click(screen.getByRole("button", { name: "Run Now" }));
    expect(await screen.findByText("该主题已有批次在队列中或正在运行。")).toBeInTheDocument();
  });

  it("supports multiple query editing", async () => {
    mockFetch();
    render(<DiscoveryConsole />);
    await screen.findByText("AI Dental Front Desk");
    await userEvent.click(screen.getByRole("button", { name: "+ Add query" }));
    expect(screen.getByLabelText("Query 2")).toBeInTheDocument();
  });
});
