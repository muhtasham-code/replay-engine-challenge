"""Stateful ARE business tools and action-dependent director. No policy learner."""

from __future__ import annotations

import copy
import hashlib
import json
import random

from are.simulation.apps.app import App
from are.simulation.apps.email_client import EmailClientApp, EmailFolderName
from are.simulation.environment import Environment, EnvironmentConfig
from are.simulation.utils import make_serializable

from .world import START, LogicalClock


class RecordsApp(App):
    def __init__(self, name, facts):
        super().__init__(name)
        self.facts = copy.deepcopy(facts)
        self.offers = []
        self.approvals = []
        self.outcomes = []

    def get_state(self):
        return copy.deepcopy(
            {
                "facts": self.facts,
                "offers": self.offers,
                "approvals": self.approvals,
                "outcomes": self.outcomes,
            }
        )


class CompanyWorld:
    def __init__(self, spec, seed, reconstruction=None):
        self.spec, self.seed = copy.deepcopy(spec), seed
        self.task = copy.deepcopy(spec["task"])
        self.facts = copy.deepcopy(reconstruction or {})
        self.clock = LogicalClock()
        self.deadline = self.task["deadline"]
        self.env = Environment(EnvironmentConfig(start_time=START, verbose=False))
        self.env.time_manager = self.clock
        self.mail = EmailClientApp(name="Emails", user_email="agent@example.test")
        self.apps = {
            service: RecordsApp(service, {}) for service in ("crm", "billing", "usage")
        }
        for field, fact in self.facts.items():
            service = self.source_service(field)
            if service in self.apps:
                self.apps[service].facts[field] = copy.deepcopy(fact)
        self.env.register_apps([self.mail, *self.apps.values()])
        for app in (self.mail, *self.apps.values()):
            app.rng = random.Random(
                int(hashlib.sha256(f"{seed}:{app.name}".encode()).hexdigest(), 16)
            )
        self.rng = random.Random(seed)
        self.pending, self.events, self.messages = [], [], []
        self.counter = 0
        self.completed = False
        self.initial_state = self.state()

    @staticmethod
    def source_service(field):
        if field.startswith(("contact", "account", "renewal")):
            return "crm"
        if field.startswith("usage"):
            return "usage"
        if field.startswith("approval"):
            return "mail"
        return "billing"

    @property
    def now(self):
        return self.clock.now

    def state(self):
        return make_serializable(
            {
                "facts": self.facts,
                "apps": {name: app.get_state() for name, app in self.apps.items()},
                "Emails": self.mail.get_state(),
                "pending": self.pending,
                "messages": self.messages,
                "completed": self.completed,
                "logical_time": self.now,
                "seed": self.seed,
            }
        )

    def log(self, kind, payload, provenance):
        self.events.append(
            {
                "sequence": len(self.events),
                "logical_time": self.now,
                "kind": kind,
                "payload": copy.deepcopy(payload),
                "provenance": provenance,
            }
        )

    def schedule(self, delay, reply):
        self.counter += 1
        self.pending.append(
            {"due": self.now + delay, "order": self.counter, "reply": reply}
        )
        self.pending.sort(key=lambda event: (event["due"], event["order"]))

    def director(self, action, arguments, result):
        # Response depends on recipient, intent, actual written offer/amount and
        # prior mutations. It is not a fixed list indexed by step number.
        if action == "message":
            actor = arguments["to"]
            persona = self.spec["people"][actor]
            delay = persona["delay"] + self.rng.randint(0, 60)
            if (
                arguments["intent"] == "approve"
                and actor == "operator"
                and arguments.get("reason")
            ):
                approved = arguments["discount"] <= persona["approval_limit"]
                self.schedule(
                    delay,
                    {
                        "intent": "approve",
                        "approved": approved,
                        "discount": arguments["discount"],
                        "actor": "operator",
                        "evidence": ["simulated:operator/approval_limit"],
                    },
                )
            elif arguments["intent"] == "clarify" and actor == "operator":
                consent = (
                    random.Random(self.seed).choice(persona["consent_choices"])
                    if "consent_choices" in persona
                    else persona["consent"]
                )
                self.schedule(
                    delay,
                    {
                        "intent": "clarify",
                        "field": arguments["field"],
                        "value": consent,
                        "actor": "operator",
                        "evidence": ["simulated:operator/consent"],
                    },
                )
            elif arguments["intent"] == "offer" and actor == "customer":
                offer = next(
                    (
                        item
                        for item in self.apps["billing"].offers
                        if item["id"] == arguments["offer_id"]
                    ),
                    None,
                )
                if offer and offer["discount"] == arguments["discount"]:
                    allowed = self.facts["contact.allowed"]["value"]
                    accepted = (
                        allowed is True
                        and arguments["discount"] >= persona["minimum_discount"]
                    )
                    self.schedule(
                        delay,
                        {
                            "intent": "accepted" if accepted else "declined",
                            "actor": "customer",
                            "offer_id": offer["id"],
                            "evidence": ["simulated:customer/response"],
                        },
                    )
        while self.pending and self.pending[0]["due"] <= self.now:
            event = self.pending.pop(0)
            reply = event["reply"]
            self.messages.append(copy.deepcopy(reply))
            self.mail.create_and_add_email(
                sender=reply["actor"] + "@example.test",
                recipients=[self.mail.user_email],
                subject=reply["intent"],
                content=json.dumps(reply, sort_keys=True),
            )
            if reply["intent"] == "approve" and reply["approved"]:
                self.apps["billing"].approvals.append(
                    {
                        "discount": reply["discount"],
                        "at": self.now,
                        "evidence": reply["evidence"],
                    }
                )
            if reply["intent"] == "clarify":
                field = reply["field"]
                fact = {
                    "value": reply["value"],
                    "status": "simulated",
                    "evidence": reply["evidence"],
                    "reason": "operator clarification",
                }
                self.facts[field] = fact
                self.apps[self.source_service(field)].facts[field] = copy.deepcopy(fact)
            if reply["intent"] == "accepted":
                offer = next(
                    item
                    for item in self.apps["billing"].offers
                    if item["id"] == reply["offer_id"]
                )
                offer["accepted_at"] = self.now
            self.log("person", reply, reply["evidence"])
        self.log(
            "director",
            {"pending_count": len(self.pending)},
            ["simulated:action-dependent-director"],
        )

    def act(self, action, arguments):
        if self.completed or len(self.events) > 500:
            raise ValueError("run complete or budget exhausted")
        if action == "lookup":
            service = arguments["service"]
            result = {
                field: copy.deepcopy(fact)
                for field, fact in self.facts.items()
                if self.source_service(field) == service
            }
        elif action == "inbox":
            result = copy.deepcopy(self.messages)
        elif action == "message":
            if arguments["to"] not in self.spec["people"]:
                raise ValueError("unknown recipient")
            if (
                arguments["intent"] == "clarify"
                and arguments.get("field") != "contact.allowed"
            ):
                raise ValueError("unsupported clarification field")
            result = self.mail.send_email(
                recipients=[arguments["to"] + "@example.test"],
                subject=arguments["intent"],
                content=json.dumps(arguments, sort_keys=True),
            )
        elif action == "offer":
            if (
                not isinstance(arguments["discount"], (int, float))
                or not 0 <= arguments["discount"] <= 100
            ):
                raise ValueError("invalid discount")
            result = {
                "id": f"offer-{len(self.apps['billing'].offers) + 1}",
                "discount": arguments["discount"],
                "at": self.now,
                "account_ref": self.task["account_ref"],
            }
            self.apps["billing"].offers.append(copy.deepcopy(result))
        elif action == "summary":
            result = self.mail.send_email(
                recipients=["owner@example.test"],
                subject="Outcome",
                content=json.dumps(arguments, sort_keys=True),
            )
            self.apps["crm"].outcomes.append(copy.deepcopy(arguments))
        elif action == "wait":
            target = (
                min(self.pending[0]["due"], self.deadline)
                if self.pending
                else self.deadline
            )
            if target <= self.now:
                raise ValueError("no future runnable event")
            self.clock.now = target
            self.env.current_time = self.clock.time()
            result = {"now": self.now}
        elif action == "complete":
            self.completed = True
            result = {"complete": True}
        else:
            raise ValueError("unsupported action")
        self.log(
            "action",
            {"action": action, "arguments": arguments, "result": result},
            ["executed:ARE-company-adapter"],
        )
        self.director(action, arguments, result)
        return result

    def evaluate(self):
        raise NotImplementedError("Inject evaluation in the trusted replay broker")

    def trace(self, version):
        return {
            "scenario_id": self.spec["id"],
            "seed": self.seed,
            "harness_version": version,
            "initial_state": self.initial_state,
            "final_state": self.state(),
            "events": self.events,
            "model": {"provider": "none", "name": "workflow-runtime"},
            "budgets": {"events": 500},
            "evaluator": {"name": "injected-outcomes"},
            **self.evaluate(),
        }
