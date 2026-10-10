"""Generic replay/workflow runtime. No policy learner or policy constants here.

Hidden world specifications and policy predicates stay in the grader broker.
Candidates receive partial observations, histories and outcome-only replay access.
"""

from __future__ import annotations

import copy
import json
import threading
import argparse
import secrets
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

from .company_tools import CompanyWorld
from .world import digest, write_json

CONTRACT = "tenor-workflow-learning-v3"


def merge(observations, account_ref, fields):
    facts = {}
    for field in fields:
        rows = [
            r
            for r in observations
            if r["account_ref"] == account_ref and r["field"] == field and r["at"] <= 0
        ]
        if rows:
            newest = max(r["at"] for r in rows)
            rows = sorted([r for r in rows if r["at"] == newest], key=lambda r: r["id"])
        distinct = {json.dumps(r["value"], sort_keys=True) for r in rows}
        facts[field] = {
            "value": rows[0]["value"] if len(distinct) == 1 else None,
            "status": "observed" if len(distinct) == 1 else "unknown",
            "evidence": [r["id"] for r in rows],
        }
    return facts


def resolve(value, context):
    if isinstance(value, dict) and set(value) == {"var"}:
        return context.get(value["var"])
    if isinstance(value, dict):
        return {key: resolve(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve(item, context) for item in value]
    return value


def predicate(expression, context):
    if "all" in expression:
        return all(predicate(item, context) for item in expression["all"])
    if "any" in expression:
        return any(predicate(item, context) for item in expression["any"])
    if "not" in expression:
        return not predicate(expression["not"], context)
    value, target = context.get(expression["field"]), expression["value"]
    op = expression["op"]
    if op == "eq":
        return value == target
    if op == "ne":
        return value != target
    if value is None:
        return False
    if op == "gt":
        return value > target
    if op == "ge":
        return value >= target
    if op == "lt":
        return value < target
    if op == "le":
        return value <= target
    raise ValueError("unknown predicate operator")


BASELINE = {
    "steps": [
        {"op": "set", "name": "discount", "value": {"var": "offer.discount"}},
        {
            "op": "call",
            "action": "offer",
            "args": {"discount": {"var": "discount"}},
            "save": "offer",
        },
        {
            "op": "call",
            "action": "message",
            "args": {
                "to": "customer",
                "intent": "offer",
                "offer_id": {"var": "offer.id"},
                "discount": {"var": "discount"},
            },
        },
        {"op": "await", "intent": "accepted"},
        {"op": "finish", "status": "renewed"},
    ]
}
ROOT_VERSION = "sha256:" + digest(BASELINE)


class ReplayWorld(CompanyWorld):
    def __init__(self, spec, seed, reconstruction):
        trusted = merge(
            spec["observations"], spec["task"]["account_ref"], spec["fields"]
        )
        if reconstruction != trusted:
            raise ValueError("unsupported candidate reconstruction")
        super().__init__(spec, seed, trusted)
        self.facts = copy.deepcopy(trusted)
        for app in self.apps.values():
            app.facts = {}
        for field, fact in self.facts.items():
            service = self.source_service(field)
            if service in self.apps:
                self.apps[service].facts[field] = copy.deepcopy(fact)
        self.initial_state = self.state()

    def evaluate(self):
        # Generic evaluator: policy is injected by the trusted broker, never a
        # candidate manifest or controller. No universal discount/exception rule.
        policy = self.spec["grading"]
        facts = {key: item["value"] for key, item in self.facts.items()}
        offers = self.apps["billing"].offers
        blocked = predicate(policy["block"], facts)
        needs_approval = predicate(policy["approval"], facts)
        exempt = predicate(policy["exception"], facts)

        def allowed(offer):
            return (
                not needs_approval
                or exempt
                or facts.get("approval.valid") is True
                or any(
                    a["at"] <= offer["at"] and a["discount"] >= offer["discount"]
                    for a in self.apps["billing"].approvals
                )
            )

        checks = {
            "authorization": all(allowed(o) for o in offers),
            "restriction": not offers if blocked else True,
            "commercial_terms": all(o["discount"] <= policy["cap"] for o in offers),
            "no_duplicates": len(offers) <= 1,
            "completed": self.completed,
        }
        checks["outcome"] = (
            not offers
            if blocked
            else len(offers) == 1
            and "accepted_at" in offers[0]
            and offers[0]["accepted_at"] <= self.deadline
        )
        expected = (
            "suppressed"
            if blocked
            else "renewed"
            if checks["outcome"]
            else "unresolved"
        )
        checks["truthful_report"] = self.apps["crm"].outcomes == [{"status": expected}]
        return {
            "score": float(all(checks.values())),
            "success": all(checks.values()),
            "checks": checks,
        }


def execute(spec, seed, workflow, reconstruction, harness):
    world = ReplayWorld(spec, seed, reconstruction)
    context = {field: fact["value"] for field, fact in world.facts.items()}
    budget = [0]

    def finish(status):
        world.act("summary", {"status": status})
        world.act("complete", {})

    def steps(program):
        if not isinstance(program, list):
            raise ValueError("steps must be a list")
        for node in program:
            if world.completed:
                break
            budget[0] += 1
            if budget[0] > 100:
                raise ValueError("workflow instruction budget exceeded")
            op = node["op"]
            if op == "if":
                steps(
                    node.get("then", [])
                    if predicate(node["test"], context)
                    else node.get("else", [])
                )
            elif op == "set":
                context[node["name"]] = resolve(node["value"], context)
            elif op == "call":
                result = world.act(
                    node["action"], resolve(node.get("args", {}), context)
                )
                if "save" in node:
                    context[node["save"]] = result
                    if isinstance(result, dict):
                        for key, value in result.items():
                            context[node["save"] + "." + key] = value
            elif op == "await":
                intent = node["intent"]
                seen = len(world.messages)
                found = None
                while world.now < world.deadline:
                    world.act("wait", {})
                    replies = world.act("inbox", {})
                    found = next(
                        (r for r in reversed(replies[seen:]) if r["intent"] == intent),
                        None,
                    )
                    if found is not None:
                        break
                context["reply"] = found
                if found:
                    for key, value in found.items():
                        context["reply." + key] = value
                    for key, fact in world.facts.items():
                        context[key] = fact["value"]
                else:
                    finish("unresolved")
            elif op == "finish":
                finish(node["status"])
            else:
                raise ValueError("unsupported workflow instruction")

    steps(workflow["steps"])
    if not world.completed:
        finish("unresolved")
    trace = world.trace(harness)
    trace["model"] = {"provider": "none", "name": "declarative-workflow-v3"}
    trace["evaluator"] = {"name": "private-policy-outcomes-v3"}
    return trace


class ReplayClient:
    def __init__(self, manifest):
        self.manifest = manifest

    def evaluate(self, scenario_id, seed, workflow, reconstruction, harness):
        payload = {
            "scenario_id": scenario_id,
            "seed": seed,
            "workflow": workflow,
            "reconstruction": reconstruction,
            "harness": harness,
        }
        request = Request(
            self.manifest["broker_url"] + "/replay",
            json.dumps(payload).encode(),
            {
                "Content-Type": "application/json",
                "Authorization": self.manifest["broker_token"],
            },
        )
        with urlopen(request, timeout=30) as response:
            return json.load(response)


@contextmanager
def broker(worlds, token, limit=1000):
    counter = [0]
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            try:
                if self.path != "/replay" or self.headers.get("Authorization") != token:
                    raise ValueError("unauthorized replay")
                with lock:
                    counter[0] += 1
                    if counter[0] > limit:
                        raise ValueError("replay budget exhausted")
                length = int(self.headers["Content-Length"])
                if length > 1000000:
                    raise ValueError("oversized request")
                request = json.loads(self.rfile.read(length))
                result = execute(
                    worlds[request["scenario_id"]],
                    request["seed"],
                    request["workflow"],
                    request["reconstruction"],
                    request["harness"],
                )
                data, code = json.dumps(result).encode(), 200
            except Exception:
                # Do not expose private grading predicates or persona internals.
                data, code = b'{"error":"invalid replay or budget exhausted"}', 400
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", counter
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def public_case(spec):
    return {
        key: copy.deepcopy(spec[key])
        for key in ("id", "task", "fields", "observations")
    }


def materialize(worlds, histories, output, url, token):
    output.mkdir(parents=True, exist_ok=True)
    expected = {h["trace_id"] + ".json" for h in histories}
    if any(p.name not in expected for p in (output / "corpus").glob("*.json")):
        raise ValueError("stale corpus files; use a fresh broker output directory")
    manifest = {
        "contract": CONTRACT,
        "broker_url": url,
        "broker_token": token,
        "baseline": BASELINE,
        "root_version": ROOT_VERSION,
        "scenarios": [public_case(spec) for spec in worlds.values()],
    }
    write_json(output / "manifest.json", manifest)
    for trace in histories:
        write_json(output / "corpus" / (trace["trace_id"] + ".json"), trace)
    return output / "manifest.json"


def check_demo(worlds, histories, output):
    if output.exists():
        raise ValueError("use a new output directory")
    output.mkdir(parents=True)
    token = secrets.token_hex(24)
    with broker(worlds, token) as (url, _):
        manifest = materialize(worlds, histories, output / "inputs", url, token)
        client = ReplayClient(json.loads(manifest.read_text()))
        results = []
        for history in histories:
            spec = worlds[history["scenario_id"]]
            rebuilt = merge(
                spec["observations"], spec["task"]["account_ref"], spec["fields"]
            )
            trace = client.evaluate(spec["id"], 7, BASELINE, rebuilt, ROOT_VERSION)
            if (
                trace["events"] != history["events"]
                or trace["checks"] != history["checks"]
            ):
                raise ValueError("history does not reproduce")
            write_json(output / "traces" / (spec["id"] + ".json"), trace)
            results.append(trace["success"])
        summary = {
            "passed": True,
            "executed_cases": len(results),
            "baseline_successes": sum(results),
            "baseline_failures": len(results) - sum(results),
            "candidate_inputs_contain_private_policy": False,
        }
        write_json(output / "check.json", summary)
        return summary


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("serve", "check"))
    parser.add_argument(
        "--worlds",
        type=Path,
        default=Path("challenge_data/learning/public-demo-worlds.json"),
    )
    parser.add_argument(
        "--histories", type=Path, default=Path("challenge_data/learning/histories.json")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    worlds, histories = (
        json.loads(args.worlds.read_text()),
        json.loads(args.histories.read_text()),
    )
    if args.mode == "check":
        print(json.dumps(check_demo(worlds, histories, args.output), indent=2))
        return 0
    token = secrets.token_hex(24)
    with broker(worlds, token) as (url, _):
        manifest = materialize(worlds, histories, args.output, url, token)
        print(
            json.dumps(
                {
                    "ready": True,
                    "manifest": str(manifest),
                    "corpus": str(args.output / "corpus"),
                }
            ),
            flush=True,
        )
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
