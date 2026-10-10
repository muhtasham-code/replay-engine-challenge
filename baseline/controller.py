"""Frozen, intentionally imperfect controller. Not an LLM or an oracle.

This is the baseline executable, not the candidate improvement loop. It accepts
a declared hook so the candidate can change completion behavior without editing
the baseline. World/tool implementations and scoring are separate.
"""


def run(world, hook):
    world.act("request", {})
    for _ in range(30):
        replies = world.act("read", {})
        acceptable = [r for r in replies if not hook.get("require_final_reply", False) or r["final"]]
        if acceptable:
            reply = acceptable[-1]
            if reply["status"] != "cancelled":
                world.act("book", {"slot": reply["slot"]})
            world.act("summary", {"status": reply["status"], "slot": reply.get("slot")})
            world.act("complete", {})
            return
        if world.now >= world.deadline:
            if not hook.get("suppress_unresolved_summary", False):
                world.act("summary", {"status": "unresolved", "slot": None})
            world.act("complete", {})
            return
        world.act("wait", {})
    raise RuntimeError("controller exceeded the action budget")
