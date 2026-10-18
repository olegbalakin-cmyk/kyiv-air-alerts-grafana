#!/usr/bin/env python3
"""Fail-closed deterministic GitHub Actions dispatch/workflow_run evaluator.

Supported expression subset: quoted strings, true/false/null, context paths,
==, !=, !, &&, ||, parentheses, always/success/failure/cancelled().
Unrecognized syntax/functions or missing context => UNKNOWN; never pass.
Job if without a status function has the implicit success() guard.
No network, service invocation, or mutation operations in this module.
"""
import copy
import json
import re
import subprocess
from pathlib import Path
import yaml
from wcmatch import glob

MONITOR = ".github/workflows/explosion-monitor-wip.yml"
WIP = "multicity-wip-2026-09-16"
BASE = "1a8b57553ba66319db326d65080ade93ae6ca01c"
PREDECESSOR = "f22c64f5fb55d690f50c60db9d1b203d0e7faf21"
PIN = "2c16b69dd3261a16cb08c9cf825a4f150cf76d11"
HOLD = "$" + "{{ false }}"
UNKNOWN = object()
TOKEN = re.compile(r"\s*(?:('(?:[^']|'')*')|([A-Za-z_][A-Za-z0-9_.-]*)|(&&|\|\||==|!=|[!()]))")
STATUSES = {"always", "success", "failure", "cancelled"}

def run_git(*args, check=True):
    p = subprocess.run(["git", *args], capture_output=True, text=True)
    if check and p.returncode:
        raise RuntimeError("git " + " ".join(args) + ": " + p.stderr[:350])
    return p.stdout if p.returncode == 0 else None

def blob(ref, path):
    # Deliberately preserve ALL source bytes, including terminal newline.
    return run_git("show", ref + ":" + path, check=False)

def source(ref, path):
    value = blob(ref, path)
    return parse(value) if value is not None else None

def parse(content):
    if content is None:
        return None
    o = yaml.load(content, Loader=yaml.BaseLoader)
    if not isinstance(o, dict):
        raise ValueError("workflow root not mapping")
    if "on" not in o or "jobs" not in o or not isinstance(o["on"], dict):
        raise ValueError("workflow must have parsed on and jobs")
    if not isinstance(o["jobs"], dict):
        raise ValueError("jobs not mapping")
    return o

def matches(value, patterns):
    if isinstance(patterns, str):
        patterns = [patterns]
    state = False
    for pat in patterns:
        negative = pat.startswith("!")
        if glob.globmatch(value, pat[1:] if negative else pat, flags=glob.GLOBSTAR | glob.DOTMATCH):
            state = not negative
    return state

def event_context(kind="workflow_dispatch", *, head_sha=None, branch=WIP,
                  conclusion="success", workflow="Monitor explosion metric WIP", default_branch="main"):
    ev = {"workflow_run": {"head_branch": branch, "name": workflow}}
    if head_sha is not None:
        ev["workflow_run"]["head_sha"] = head_sha
    if conclusion is not None:
        ev["workflow_run"]["conclusion"] = conclusion
    execution_branch = default_branch if kind == "workflow_run" else branch
    return {"github": {"event_name": kind, "ref": "refs/heads/" + execution_branch,
                       "ref_name": execution_branch, "event": ev}}

def bool3(x):
    if x is UNKNOWN:
        return UNKNOWN
    if isinstance(x, bool):
        return x
    if x is None:
        return False
    if isinstance(x, (str, int, float)):
        return bool(x)
    return UNKNOWN

def and3(a, b):
    a, b = bool3(a), bool3(b)
    if a is False or b is False:
        return False
    if a is UNKNOWN or b is UNKNOWN:
        return UNKNOWN
    return True

def or3(a, b):
    a, b = bool3(a), bool3(b)
    if a is True or b is True:
        return True
    if a is UNKNOWN or b is UNKNOWN:
        return UNKNOWN
    return False

def expr_ast(raw):
    s = str(raw).strip()
    if s.startswith("$" + "{{") and s.endswith("}}"):
        s = s[3:-2].strip()
    tokens, i = [], 0
    while i < len(s):
        if not s[i:].strip():
            break
        m = TOKEN.match(s, i)
        if m is None or m.end() <= i:
            raise ValueError("unsupported token at " + repr(s[i:i+30]))
        tokens.append((m.group(1) and "str" or m.group(2) and "ident" or "op", next(z for z in m.groups() if z is not None)))
        i = m.end()
    k = 0
    def peek():
        return tokens[k][1] if k < len(tokens) else None
    def eat(expected=None):
        nonlocal k
        if k >= len(tokens) or (expected is not None and peek() != expected):
            raise ValueError("incomplete/invalid expression")
        v = tokens[k]
        k += 1
        return v
    def atom():
        t = peek()
        if t == "!":
            eat("!")
            return ("not", atom())
        if t == "(":
            eat("(")
            v = lor()
            eat(")")
            return v
        kind, val = eat()
        if kind == "str":
            return ("lit", val[1:-1].replace("''", "'"))
        if kind != "ident":
            raise ValueError("unsupported atom")
        if peek() == "(":
            eat("(")
            eat(")")
            if val not in STATUSES:
                raise ValueError("unsupported function " + val)
            return ("call", val)
        if val in ("true", "false", "null"):
            return ("lit", {"true": True, "false": False, "null": None}[val])
        return ("var", val)
    def eq():
        left = atom()
        while peek() in ("==", "!="):
            op = eat()[1]
            left = (op, left, atom())
        return left
    def land():
        left = eq()
        while peek() == "&&":
            eat("&&")
            left = ("and", left, eq())
        return left
    def lor():
        left = land()
        while peek() == "||":
            eat("||")
            left = ("or", left, land())
        return left
    if not tokens:
        raise ValueError("blank expression")
    tree = lor()
    if k != len(tokens):
        raise ValueError("remaining unparsed tokens")
    return tree

def has_status(tree):
    if tree[0] == "call" and tree[1] in STATUSES:
        return True
    return any(has_status(k) for k in tree[1:] if isinstance(k, tuple))

def eval_tree(tree, ctx, need_status):
    op = tree[0]
    if op == "lit":
        return tree[1]
    if op == "var":
        val = ctx
        for part in tree[1].split("."):
            if not isinstance(val, dict) or part not in val:
                return UNKNOWN
            val = val[part]
        return val
    if op == "call":
        if tree[1] == "always":
            return True
        vals = list(need_status.values())
        # A known failure must not be overwritten by an unrelated UNKNOWN.
        # An implicit success() is false for failed, cancelled or skipped needs.
        if tree[1] == "success":
            if any(v in ("failure", "cancelled", "skipped") for v in vals):
                return False
            return UNKNOWN if any(v == "unknown" for v in vals) else True
        if tree[1] == "failure":
            if any(v == "failure" for v in vals):
                return True
            return UNKNOWN if any(v == "unknown" for v in vals) else False
        if tree[1] == "cancelled":
            if any(v == "cancelled" for v in vals):
                return True
            return UNKNOWN if any(v == "unknown" for v in vals) else False

    if op == "not":
        x = bool3(eval_tree(tree[1], ctx, need_status))
        return UNKNOWN if x is UNKNOWN else not x
    if op in ("and", "or"):
        a = eval_tree(tree[1], ctx, need_status)
        b = eval_tree(tree[2], ctx, need_status)
        return and3(a, b) if op == "and" else or3(a, b)
    if op in ("==", "!="):
        a = eval_tree(tree[1], ctx, need_status)
        b = eval_tree(tree[2], ctx, need_status)
        if a is UNKNOWN or b is UNKNOWN:
            return UNKNOWN
        eqv = a == b
        return eqv if op == "==" else not eqv
    return UNKNOWN

def evaluate(raw, ctx, needs=None, implicit=True):
    needs = needs or {}
    if raw is None:
        return (bool3(eval_tree(("call", "success"), ctx, needs)), "implicit_success")
    try:
        ast = expr_ast(raw)
        v = bool3(eval_tree(ast, ctx, needs))
        if implicit and not has_status(ast):
            v = and3(bool3(eval_tree(("call", "success"), ctx, needs)), v)
        return v, "parsed"
    except (ValueError, TypeError, IndexError):
        return UNKNOWN, "unsupported_expression"

def flag(x):
    return "UNKNOWN" if x is UNKNOWN else ("TRUE" if x else "FALSE")

def effects(job, wf):
    text = json.dumps(job, ensure_ascii=False)
    return {
        "ukrainealarm_secret_reference": "UKRAINEALARM_API_TOKEN" in text,
        "database_secret_reference": "DATABASE_URL" in text or "PHASE1_PROD_SHADOW_DATABASE_URL" in text,
        "possible_git_write": bool(re.search(r"\bgit push\b|\bgh api\b|\bgit commit\b", text)),
        "workflow_contents_write": (job.get("permissions", wf.get("permissions", {})) or {}).get("contents") == "write"
            if isinstance(job.get("permissions", wf.get("permissions", {})), dict) else False,
        "invokes_monitor": "monitor_explosion_candidates.py" in text
    }

def job_matrix(wf, ctx, force_needs=None, job_results=None):
    """Compute eligibility separately from actual outcomes.

    With no supplied outcome an executable job has UNKNOWN result. It is never
    implicitly promoted to success for dependent jobs. The ancestor status set
    supports failure()/cancelled() in chained needs.
    """
    jobs = wf["jobs"]
    statuses, details, ancestors = {}, {}, {}
    allowed = {"success", "failure", "cancelled", "skipped", "unknown"}
    forced = job_results or {}
    if any(v not in allowed for v in forced.values()):
        raise ValueError("invalid modeled job result")
    todo = set(jobs)
    while todo:
        advanced = False
        for name in sorted(todo):
            j = jobs[name]
            needs = j.get("needs", [])
            needs = [needs] if isinstance(needs, str) else (needs or [])
            if not all(n in statuses for n in needs):
                continue
            needs_status = {n: statuses[n] for n in needs}
            if force_needs:
                needs_status.update({n: v for n, v in force_needs.items() if n in needs})
            all_relevant = {}
            for n in needs:
                all_relevant.update(ancestors.get(n, {}))
                all_relevant[n] = needs_status[n]
            effective_ctx = copy.deepcopy(ctx)
            effective_ctx["needs"] = {n: {"result": v, "outputs": {}} for n, v in needs_status.items()}
            condition = j.get("if")
            v, kind = evaluate(condition, effective_ctx, all_relevant)
            state = "JOB_EXECUTABLE" if v is True else ("JOB_SKIPPED" if v is False else "UNKNOWN")
            actual = (forced.get(name, "unknown") if v is True
                      else "skipped" if v is False else "unknown")
            statuses[name] = actual
            ancestors[name] = all_relevant
            details[name] = {"state": state, "if": condition,
                             "condition_evaluation": flag(v), "condition_parse": kind,
                             "needs": needs, "needs_actual_results": needs_status,
                             "modeled_job_result": actual, "potential_effects": effects(j, wf)}
            todo.remove(name)
            advanced = True
            break
        if not advanced:
            for name in sorted(todo):
                statuses[name] = "unknown"
                details[name] = {"state": "UNKNOWN", "reason": "cycle_or_missing_needs",
                                 "needs": jobs[name].get("needs"), "modeled_job_result": "unknown"}
            break
    return details

def can_run(wf, *, default_registered=False, ref_present=True, dispatch=True, ctx=None):
    if not default_registered:
        return {"eligible": False, "reason": "not_registered_on_default_branch", "jobs": {}}
    if not ref_present or wf is None:
        return {"eligible": False, "reason": "selected_ref_has_no_workflow", "jobs": {}}
    if dispatch and "workflow_dispatch" not in wf["on"]:
        return {"eligible": False, "reason": "selected_workflow_has_no_dispatch", "jobs": {}}
    jobs = job_matrix(wf, ctx or event_context())
    return {"eligible": True, "reason": "selected_ref_workflow_version", "jobs": jobs,
            "executable": sorted(k for k, v in jobs.items() if v["state"] == "JOB_EXECUTABLE"),
            "unknown": sorted(k for k, v in jobs.items() if v["state"] == "UNKNOWN")}

def run_event(wf, name, upstream, activity="completed", default_present=True, depth=1,
              job_results=None):
    if not default_present or wf is None:
        return {"state": "DOWNSTREAM_BLOCKED", "reason": "consumer_absent_on_default_branch"}
    if depth > 3:
        return {"state": "DOWNSTREAM_BLOCKED", "reason": "workflow_run_depth_gt_3"}
    trigger = wf["on"].get("workflow_run")
    if not isinstance(trigger, dict):
        return {"state": "DOWNSTREAM_BLOCKED", "reason": "no_workflow_run_listener"}
    names = trigger.get("workflows") or []
    if isinstance(names, str):
        names = [names]
    if not matches(name, names):
        return {"state": "EVENT_NOT_CREATED", "reason": "upstream_workflow_name_mismatch"}
    types = trigger.get("types") or ["completed", "requested", "in_progress"]
    if isinstance(types, str):
        types = [types]
    if activity not in types:
        return {"state": "EVENT_NOT_CREATED", "reason": "activity_filter_mismatch"}
    branch = upstream.get("head_branch")
    if ("branches" in trigger or "branches-ignore" in trigger) and branch is None:
        return {"state": "UNKNOWN", "reason": "upstream_branch_unavailable"}
    if "branches" in trigger and not matches(branch, trigger["branches"]):
        return {"state": "EVENT_NOT_CREATED", "reason": "branch_filter_mismatch"}
    if "branches-ignore" in trigger and branch and matches(branch, trigger["branches-ignore"]):
        return {"state": "EVENT_NOT_CREATED", "reason": "branch_excluded"}
    ctx = event_context("workflow_run", head_sha=upstream.get("head_sha"),
                        branch=branch or "unknown", conclusion=upstream.get("conclusion"),
                        workflow=name)
    jobs = job_matrix(wf, ctx, job_results=job_results)
    return {"state": "EVENT_CREATED", "reason": "matching_workflow_run",
            "depth": depth, "jobs": jobs,
            "jobs_executable": sorted(k for k, j in jobs.items() if j["state"] == "JOB_EXECUTABLE"),
            "jobs_unknown": sorted(k for k, j in jobs.items() if j["state"] == "UNKNOWN")}
