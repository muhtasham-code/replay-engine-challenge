"""Executed PUBLIC example only. Grading policies differ and remain private.

This is fixture construction, not a proposal, discovery or revision algorithm.
"""

import copy
import json
from pathlib import Path

from replay_challenge.workflow import (
    BASELINE,
    ROOT_VERSION,
    execute,
    merge,
    public_case,
)
from replay_challenge.world import write_json, digest


def make_pack(approval, exception, block, cap, examples, prefix="example"):
    worlds, histories = {}, []
    fields = [
        "account.name",
        "offer.discount",
        "contact.allowed",
        "approval.valid",
        "usage.critical",
        "renewal.hours_left",
        "account.risk",
        "contract.signed",
    ]
    for index, example in enumerate(examples):
        values = {
            "account.name": "Acme",
            "offer.discount": 24,
            "contact.allowed": True,
            "approval.valid": False,
            "usage.critical": False,
            "renewal.hours_left": 72,
            "account.risk": "normal",
            "contract.signed": True,
            **example["facts"],
        }
        identity = prefix + "-" + digest({"index": index, "values": values})[:10]
        account = identity + ".test"
        observations = [
            {
                "id": f"record-{index}-{j}",
                "account_ref": account,
                "field": field,
                "value": value,
                "at": -300,
                "source": "recorded:" + field.split(".")[0],
            }
            for j, (field, value) in enumerate(values.items())
        ]
        observations.extend(
            [
                {
                    "id": f"stale-{index}",
                    "account_ref": account,
                    "field": "offer.discount",
                    "value": 0,
                    "at": -999,
                    "source": "billing",
                },
                {
                    "id": f"future-{index}",
                    "account_ref": account,
                    "field": "offer.discount",
                    "value": 99,
                    "at": 1,
                    "source": "billing",
                },
                {
                    "id": f"unrelated-{index}",
                    "account_ref": "other.test",
                    "field": "account.name",
                    "value": "Acme",
                    "at": 0,
                    "source": "crm",
                },
            ]
        )
        spec = {
            "id": identity,
            "fields": fields,
            "observations": observations,
            "task": {
                "account_ref": account,
                "objective": "Complete this renewal safely and report its result.",
                "deadline": 7200 if example.get("urgent") else 604800,
            },
            "people": {
                "operator": {"delay": 172800, "approval_limit": 100, "consent": True},
                "customer": {"delay": 60, "minimum_discount": 0},
            },
            "grading": {
                "approval": approval,
                "exception": exception,
                "block": block,
                "cap": cap,
            },
        }
        worlds[identity] = spec
        trace = execute(
            spec, 7, BASELINE, merge(observations, account, fields), ROOT_VERSION
        )
        history = {
            "trace_id": identity + "-history",
            "scenario_id": identity,
            "observations": observations,
            "fields": fields,
            "task": spec["task"],
            "events": trace["events"],
            "checks": trace["checks"],
            "outcome": "success" if trace["success"] else "failure",
            "feedback": example.get("feedback", ""),
            "provenance": "executed synthetic baseline",
        }
        histories.append(history)
    return worlds, histories


def demo():
    approval = {"field": "offer.discount", "op": "gt", "value": 12}
    exception = {
        "all": [
            {"field": "usage.critical", "op": "eq", "value": True},
            {"field": "renewal.hours_left", "op": "le", "value": 2},
        ]
    }
    block = {"field": "contact.allowed", "op": "eq", "value": False}
    examples = [
        {
            "facts": {},
            "feedback": "Discounts beyond 12 percent need review before the offer is created.",
        },
        {"facts": {"usage.critical": True, "renewal.hours_left": 1}, "urgent": True},
        {"facts": {"usage.critical": True, "renewal.hours_left": 8}},
        {"facts": {"renewal.hours_left": 1}},
        {"facts": {"approval.valid": True}},
        {"facts": {"offer.discount": 12}},
        {"facts": {"offer.discount": 0}},
        {
            "facts": {"contact.allowed": False, "approval.valid": True},
            "feedback": "This customer opted out; they should not receive an offer.",
        },
        {
            "facts": {"offer.discount": 45, "approval.valid": True},
            "feedback": "Our commercial limit is 30 percent. The offer exceeded it.",
        },
        {
            "facts": {"offer.discount": 8},
            "feedback": "Always ask for approval, even for this routine renewal.",
        },
    ]
    return make_pack(approval, exception, block, 30, examples)


if __name__ == "__main__":
    worlds, histories = demo()
    root = Path("challenge_data/learning")
    write_json(root / "public-demo-worlds.json", worlds)
    write_json(root / "histories.json", histories)
    write_json(root / "cases.json", [public_case(w) for w in worlds.values()])
