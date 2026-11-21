// Independent C6 watchdog on Netlify, installed on a separate scheduler site.
// No Neon access, site-prod writes, production build, or Netlify redeploy.
// Requires an owner-issued, repository-scoped GitHub Actions:write token to act.
const API = "https://api.github.com/repos/olegbalakin-cmyk/kyiv-air-alerts-grafana";
const WORKFLOW = "update-netlify-site.yml";
const WORKFLOW_ID = 360885782;
const DATA_PATH = "kyiv-air-alerts-grafana/data/dashboard_data.json";

export const FOUR_HOURS_MS = 4 * 60 * 60 * 1000;
export const MIN_ATTEMPT_GAP_MS = FOUR_HOURS_MS + 20 * 60 * 1000;
export const MIN_PUBLICATION_AGE_MS = 5 * 60 * 60 * 1000;
export const DAILY_ATTEMPT_CAP = 6;

export const config = { schedule: "47 * * * *" }; // Netlify UTC, independent hourly poll.

function isoMillis(iso) {
  if (typeof iso !== "string" || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d/.test(iso)) {
    throw new Error("INVALID_REMOTE_TIME");
  }
  const ms = Date.parse(iso);
  if (!Number.isFinite(ms)) throw new Error("INVALID_REMOTE_TIME");
  return ms;
}

function parseRun(run) {
  if (!run || typeof run !== "object" ||
      !["schedule", "workflow_dispatch", "push"].includes(run.event) ||
      !["completed", "in_progress", "queued", "waiting", "pending", "requested"].includes(run.status)) {
    throw new Error("INVALID_RUN_STATE");
  }
  return { event: run.event, status: run.status, startedAt: isoMillis(run.created_at) };
}

// Pure, fail-closed decision: when uncertain, NEVER dispatch.
export function decide({ now, runs, lastDataCommitAt }) {
  const current = now instanceof Date ? now.getTime() : isoMillis(now);
  if (!Number.isFinite(current)) throw new Error("INVALID_NOW");
  if (!Array.isArray(runs) || runs.length === 0) throw new Error("RUN_HISTORY_MISSING");
  const relevant = runs.map(parseRun).filter(x => x.event !== "push");
  if (relevant.length === 0) throw new Error("C6_RUN_HISTORY_MISSING");
  if (relevant.some(x => x.startedAt > current + 120000)) throw new Error("FUTURE_RUN_CLOCK");
  if (relevant.some(x => x.status !== "completed")) {
    return { dispatch: false, reason: "C6_ACTIVE_OR_QUEUED" };
  }
  const latestStartedAt = Math.max(...relevant.map(x => x.startedAt));
  const startedLast24h = relevant.filter(x => x.startedAt >= current - 86400000).length;
  if (startedLast24h >= DAILY_ATTEMPT_CAP) {
    return { dispatch: false, reason: "C6_DAILY_ATTEMPT_CAP" };
  }
  const sinceAttempt = current - latestStartedAt;
  if (sinceAttempt < MIN_ATTEMPT_GAP_MS) {
    return { dispatch: false, reason: "C6_ATTEMPT_RECENT", sinceAttemptMs: sinceAttempt };
  }
  const publishedAt = isoMillis(lastDataCommitAt);
  const sincePublish = current - publishedAt;
  if (sincePublish < -120000) throw new Error("FUTURE_DATA_CLOCK");
  if (sincePublish < MIN_PUBLICATION_AGE_MS) {
    return { dispatch: false, reason: "C6_DATA_RECENT", sincePublishMs: sincePublish };
  }
  return { dispatch: true, reason: "C6_CATCHUP_REQUIRED",
           sinceAttemptMs: sinceAttempt, sincePublishMs: sincePublish };
}

function makeHeaders(token) {
  return {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    ...(token ? { Authorization: "Bearer " + token } : {}),
  };
}

async function getJson(url, fetchImpl) {
  const response = await fetchImpl(url, {
    method: "GET", headers: makeHeaders(""), cache: "no-store",
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error("GITHUB_READ_UNAVAILABLE");
  return response.json();
}

export async function checkAndMaybeDispatch({
  fetchImpl = fetch, now = new Date(), token = "", enabled = false,
} = {}) {
  // Public GitHub GETs suffice for observation. No owner token on GET.
  const runResponse = await getJson(
    API + "/actions/workflows/" + WORKFLOW_ID + "/runs?per_page=50", fetchImpl);
  if (!Array.isArray(runResponse.workflow_runs)) throw new Error("RUN_RESPONSE_INVALID");
  const commitResponse = await getJson(
    API + "/commits?sha=site-prod&path=" + encodeURIComponent(DATA_PATH) + "&per_page=1",
    fetchImpl);
  const commit = Array.isArray(commitResponse) && commitResponse[0];
  if (!commit || typeof commit.sha !== "string" || !/^[a-f0-9]{40}$/.test(commit.sha)) {
    throw new Error("DATA_COMMIT_MISSING");
  }
  const lastDataCommitAt = commit.commit?.committer?.date;
  const verdict = decide({ now, runs: runResponse.workflow_runs, lastDataCommitAt });
  if (!verdict.dispatch) return { ...verdict, action: "NONE" };
  if (!enabled) return { ...verdict, action: "DRY_RUN_ONLY" };
  if (!token || token.trim().length < 12) {
    return { ...verdict, dispatch: false, reason: "OWNER_TOKEN_MISSING", action: "NONE" };
  }

  // Re-read before dispatch to minimize races with native GitHub cron.
  // Never retry POST, because an ambiguous timeout could duplicate a run.
  const current = await getJson(
    API + "/actions/workflows/" + WORKFLOW_ID + "/runs?per_page=50", fetchImpl);
  const second = decide({ now, runs: current.workflow_runs, lastDataCommitAt });
  if (!second.dispatch) return { ...second, action: "NONE" };
  const response = await fetchImpl(
    API + "/actions/workflows/" + WORKFLOW + "/dispatches", {
      method: "POST",
      headers: { ...makeHeaders(token), "Content-Type": "application/json" },
      body: JSON.stringify({
        ref: "main",
        inputs: {
          c6_run_now: "true",
          c6_neon_git_pilot: "false",
          c6_final_prepare_only: "false",
          c6_neon_git_release: "false",
        },
      }),
      signal: AbortSignal.timeout(10000),
    },
  );
  if (response.status !== 204) throw new Error("GITHUB_DISPATCH_UNCONFIRMED");
  return { ...verdict, action: "DISPATCH_ACCEPTED" };
}

function env(key) {
  return globalThis.Netlify?.env?.get(key) ?? process.env[key] ?? "";
}

export default async () => {
  try {
    const outcome = await checkAndMaybeDispatch({
      enabled: env("C6_BACKUP_ENABLED") === "true",
      token: env("C6_BACKUP_GITHUB_TOKEN"),
    });
    // Constant labels only; never output token, API headers or data.
    console.log("C6_BACKUP_CHECK", outcome.reason, outcome.action);
  } catch {
    console.error("C6_BACKUP_FAIL_CLOSED");
  }
};
