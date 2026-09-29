"""The bridge: an AI session and a live tab, one trace.

Luna's /bridge (browser-hand, :8474) drove its own headless browser. This one
drives the real Golden Surface tabs through the relay, under the same rules as
any seat. Each step:

  observe   the tab's structures (indexed affordances) and a window of its text
  decide    one action, from a decider (an OpenAI-compatible chat endpoint)
  execute   through Relay.run_cmd — ownership, locked tabs, password refusal all apply
  record    {step, action, observation} as a bridge.step entry in the shard

The decider is configured, never assumed: GOLDEN_AI_URL (a /chat/completions
endpoint), GOLDEN_AI_KEY, GOLDEN_AI_MODEL. With none, the bridge says so (503)
and nothing else changes. Tabs on a shared (signed-in) session are refused:
their page is never sent to a decider.
"""
import json
import re

import aiohttp

MAX_STEPS = 8
TEXT_WINDOW = 1500
ITEMS_MAX = 80

SYSTEM = """You drive one browser tab toward a goal, one action per turn.
You see the page as indexed items (links, fields, buttons, selects) and a window of its text.
Answer with exactly one JSON object and nothing else, one of:
  {"action": "open", "url": "https://..."}
  {"action": "act", "index": <item i>, "kind": "tap" | "fill" | "submit", "text": "<for fill>"}
  {"action": "scroll", "from": <character offset>}
  {"action": "done", "result": "<what you found or did>"}
Items marked fingersOnly are password fields: never act on them. Stop with done as soon as the goal is met."""


class NoDecider(Exception):
    pass


class Decider:
    def __init__(self, env):
        self.url = env.get("GOLDEN_AI_URL")
        self.key = env.get("GOLDEN_AI_KEY")
        self.model = env.get("GOLDEN_AI_MODEL", "")

    @property
    def configured(self):
        return bool(self.url)

    async def decide(self, messages):
        if not self.url:
            raise NoDecider("no decider configured (GOLDEN_AI_URL)")
        headers = {"content-type": "application/json"}
        if self.key:
            headers["authorization"] = f"Bearer {self.key}"
        body = {"messages": messages, "temperature": 0}
        if self.model:
            body["model"] = self.model
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45)) as s:
            async with s.post(self.url, json=body, headers=headers) as r:
                if r.status != 200:
                    raise RuntimeError(f"decider answered HTTP {r.status}")
                data = await r.json(content_type=None)
        return data["choices"][0]["message"]["content"]


def parse_action(text):
    """The first JSON object in the decider's answer."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        raise ValueError("decider gave no JSON action")
    a = json.loads(m.group(0))
    if a.get("action") not in ("open", "act", "scroll", "done"):
        raise ValueError(f"unknown action {a.get('action')!r}")
    return a


def observation(structures, text, start, domain):
    items = (structures or {}).get("items", [])[:ITEMS_MAX]
    return {
        "url": (structures or {}).get("url"),
        "title": (structures or {}).get("title"),
        "domain": domain,
        "items": items,
        "text": {"from": start, "window": text[start:start + TEXT_WINDOW], "total": len(text)},
    }


async def run(relay, seat, tab_id, goal, steps=MAX_STEPS, decider=None, domain_of=None):
    """Run the loop. Returns {ok, goal, trace, result?, error?}."""
    decider = decider or relay.decider
    if not decider.configured:
        raise NoDecider("no decider configured (GOLDEN_AI_URL)")
    steps = max(1, min(MAX_STEPS, int(steps)))
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Goal: {goal}"}]
    trace, start, result = [], 0, None

    for step in range(1, steps + 1):
        st, s_res = await relay.run_cmd(seat, "structures", {"tab": tab_id})
        _, r_res = await relay.run_cmd(seat, "read", {"tab": tab_id})
        if st != 200:
            trace.append({"step": step, "error": s_res.get("error")})
            break
        structs = s_res.get("data") or {}
        text = ((r_res.get("data") or {}).get("text")) or ""
        obs = observation(structs, text, start, domain_of(structs.get("url")) if domain_of else None)
        messages.append({"role": "user", "content": "Observation:\n" + json.dumps(obs, ensure_ascii=False)})

        try:
            answer = await decider.decide(messages)
            action = parse_action(answer)
        except Exception as e:  # a bad answer ends the run, recorded
            rec = {"step": step, "error": f"decide: {e}"}
            trace.append(rec)
            relay.shard.append("bridge.step", seat, {"tab": tab_id, "goal": goal, **rec})
            break
        messages.append({"role": "assistant", "content": json.dumps(action)})

        outcome = None
        if action["action"] == "done":
            result = action.get("result")
        elif action["action"] == "scroll":
            start = max(0, int(action.get("from", 0)))
            outcome = {"ok": True, "from": start}
        elif action["action"] == "open":
            code, outcome = await relay.run_cmd(seat, "open", {"tab": tab_id, "url": action.get("url", "")})
        else:  # act
            code, outcome = await relay.run_cmd(seat, "act", {"tab": tab_id, "index": action.get("index"),
                                                               "kind": action.get("kind"),
                                                               "text": action.get("text", "")})
        rec = {"step": step, "action": action,
               "observation": {"url": obs["url"], "title": obs["title"], "items": len(obs["items"])},
               "outcome": {k: v for k, v in (outcome or {}).items() if k in ("ok", "error", "from")}}
        trace.append(rec)
        relay.shard.append("bridge.step", seat, {"tab": tab_id, "goal": goal, **rec})
        if result is not None:
            break
        if outcome and not outcome.get("ok"):
            messages.append({"role": "user", "content": f"That action failed: {outcome.get('error')}"})

    return {"ok": result is not None, "goal": goal, "tab": tab_id, "result": result, "trace": trace,
            "steps": len(trace)}
