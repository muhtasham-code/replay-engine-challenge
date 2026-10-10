"""Bounded ARE world adapter, director, and independent outcome evaluator.

Native ARE Email and Calendar apps own tool state. The adapter provides a
single logical clock and a deterministic scheduler instead of starting ARE's
wall-clock thread. No oracle events or oracle agent are used here.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from are.simulation.apps.calendar import CalendarApp
from are.simulation.apps.email_client import EmailClientApp
from are.simulation.environment import Environment, EnvironmentConfig
from are.simulation.time_manager import TimeManager
from are.simulation.utils import make_serializable

ROOT = Path(__file__).resolve().parents[2]
START = 1791763200.0


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


class LogicalClock(TimeManager):
    def __init__(self):
        super().__init__()
        self.now = 0.0
        self.start_time = START

    def time_passed(self):
        return self.now


class World:
    def __init__(self, spec, seed):
        self.spec = copy.deepcopy(spec)
        self.seed = seed
        self.clock = LogicalClock()
        self.env = Environment(EnvironmentConfig(start_time=START, verbose=False))
        self.env.time_manager = self.clock
        self.mail = EmailClientApp(name="Emails", user_email="agent@example.test")
        self.calendar = CalendarApp(name="Calendar")
        self.env.register_apps([self.mail, self.calendar])
        for app in (self.mail, self.calendar):
            stable_seed = int(hashlib.sha256(f"{seed}:{app.name}".encode()).hexdigest(), 16)
            app.rng = random.Random(stable_seed)
        self.rng = random.Random(seed)
        self.events = []
        self.pending = []
        self.deadline = spec["deadline"]
        self.requested = False
        self.request_time = None
        self.completed = False
        self.initial_state = self.state()

    @property
    def now(self):
        return self.clock.now

    def state(self):
        return make_serializable({
            "apps": {"Emails": self.mail.get_state(), "Calendar": self.calendar.get_state()},
            "logical_time": self.now, "pending": self.pending,
            "requested": self.requested, "completed": self.completed,
            "request_time": self.request_time,
            "scenario": self.spec, "seed": self.seed,
        })

    def log(self, kind, payload, provenance):
        self.events.append({"sequence": len(self.events), "logical_time": self.now,
                            "kind": kind, "payload": copy.deepcopy(payload), "provenance": provenance})

    def _deliver_due(self):
        while self.pending and self.pending[0]["due"] <= self.now:
            event = self.pending.pop(0)
            self.mail.create_and_add_email(sender=self.spec["operator"], recipients=[self.mail.user_email],
                                          subject="Availability", content=json.dumps(event["reply"], sort_keys=True))
            self.log("person", event["reply"], "simulated:scenario/response_plan")
        self.log("director", {"pending_count": len(self.pending)}, "simulated:director")

    def response_plan(self):
        rng = random.Random(self.seed)
        choice = rng.choice(self.spec["final_choices"])
        plan = []
        for index, template in enumerate(self.spec["response_plan"]):
            reply = copy.deepcopy(template["reply"])
            if reply["final"]:
                reply.update(choice)
            plan.append({"due": (self.request_time or 0) + template["after"] + rng.randint(0, 2), "order": index, "reply": reply})
        return sorted(plan, key=lambda item: (item["due"], item["order"]))

    def replies(self):
        from are.simulation.apps.email_client import EmailFolderName
        emails = self.mail.folders[EmailFolderName.INBOX].emails
        return [json.loads(email.content) for email in emails if email.sender == self.spec["operator"]]

    def act(self, action, arguments):
        if self.completed:
            raise ValueError("no actions allowed after completion")
        if len(self.events) > 200:
            raise ValueError("world action budget exceeded")
        if action == "request":
            if self.requested:
                raise ValueError("duplicate availability request")
            result = self.mail.send_email(recipients=[self.spec["operator"]], subject="Availability request",
                                          content=self.spec["objective"])
            self.requested = True
            self.request_time = self.now
            # Schedule only in response to a real request. Seeds vary response
            # timing and final choice; the agent cannot read this plan as a tool.
            self.pending = self.response_plan()
        elif action == "read":
            result = self.replies()
        elif action == "book":
            start = arguments["slot"]
            end = (datetime.strptime(start, "%Y-%m-%d %H:%M:%S") + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
            result = self.calendar.add_calendar_event(title=self.spec["account"] + " review",
                        start_datetime=start, end_datetime=end, attendees=[self.spec["operator"]])
        elif action == "summary":
            result = self.mail.send_email(recipients=["owner@example.test"], subject="Review outcome",
                                          content=json.dumps(arguments, sort_keys=True))
        elif action == "wait":
            target = min(self.pending[0]["due"], self.deadline) if self.pending else self.deadline
            if target <= self.now:
                raise ValueError("no runnable future event")
            self.clock.now = target
            self.env.current_time = self.clock.time()
            result = {"now": self.now}
        elif action == "complete":
            self.completed = True
            result = {"complete": True}
        else:
            raise ValueError(f"unknown action: {action}")
        self.log("action", {"action": action, "arguments": arguments, "result": result}, "executed:ARE-adapter")
        self._deliver_due()
        return result

    def evaluate(self):
        # Judge expected outcome from the independently seeded human plan, not
        # a candidate's declared score or exact tool sequence. Future replies
        # represent outstanding obligations even if the controller stops early.
        final_replies = [item["reply"] for item in self.response_plan()
                         if item["reply"]["final"] and item["due"] <= self.deadline]
        final_due = bool(final_replies)
        expected = {key: final_replies[-1][key] for key in ("status", "slot")} if final_due else {"status": "unresolved", "slot": None}
        actual_events = list(self.calendar.events.values())
        slots = [datetime.fromtimestamp(event.start_datetime, timezone.utc).strftime("%Y-%m-%d %H:%M:%S") for event in actual_events]
        wanted_slots = [expected["slot"]] if expected["status"] == "confirmed" else []
        from are.simulation.apps.email_client import EmailFolderName
        summaries = [json.loads(email.content) for email in self.mail.folders[EmailFolderName.SENT].emails
                     if email.subject == "Review outcome" and email.recipients == ["owner@example.test"]]
        checks = {"correct_calendar": slots == wanted_slots, "correct_summary": summaries == [expected],
                  "completed": self.completed, "request_sent": self.requested,
                  "deadline_respected": self.now >= self.deadline if not final_due else
                      any(reply["final"] for reply in self.replies())}
        return {"score": float(all(checks.values())), "success": all(checks.values()), "checks": checks}


def load_spec(manifest_path, row):
    root = manifest_path.parent.resolve()
    path = (root / row["path"]).resolve()
    if not path.is_relative_to(root):
        raise ValueError("scenario path escapes manifest directory")
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != row["source_sha256"]:
        raise ValueError("scenario checksum mismatch")
    return json.loads(payload)


def baseline_version():
    data = json.loads((ROOT / "challenge_data/baseline.json").read_text())
    for component in data["components"]:
        if hashlib.sha256((ROOT / component["path"]).read_bytes()).hexdigest() != component["sha256"]:
            raise ValueError("baseline component changed")
    return data["parent_version"]


def execute(spec, seed, hook=None, side="baseline", version=None):
    world = World(spec, seed)
    baseline_version()
    module_spec = importlib.util.spec_from_file_location("frozen_controller", ROOT / "baseline/controller.py")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    module.run(world, hook or {})
    return trace(world, side, version or baseline_version())


def trace(world, side, version):
    return {"scenario_id": world.spec["id"], "seed": world.seed, "side": side, "harness_version": version,
            "model": {"provider": "none", "name": "frozen-controller-v1"},
            "budgets": {"controller_iterations": 30, "world_events": 200},
            "evaluator": {"name": "ARE-outcome-v1", "success_requires_all_checks": True},
            "initial_state": world.initial_state, "final_state": world.state(), "events": world.events,
            **world.evaluate()}


def verify_trace(spec, saved):
    """Re-execute actions against fresh native ARE state; reject invented outputs."""
    world = World(spec, saved["seed"])
    for event in saved["events"]:
        if event["kind"] == "action":
            world.act(event["payload"]["action"], event["payload"]["arguments"])
    rebuilt = trace(world, saved["side"], saved["harness_version"])
    if rebuilt != saved:
        raise ValueError("trace differs from independent ARE action replay")
    if saved["side"] == "baseline" and execute(spec, saved["seed"]) != saved:
        raise ValueError("trace is not the frozen baseline execution")
