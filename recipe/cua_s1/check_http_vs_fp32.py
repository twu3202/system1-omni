"""Check a running worker's answers on the fixed input set against the fp32 reference.

    python exp/check_http_vs_fp32.py <worker url> <inputs.json> <parity dir>

README rule: over the set, the largest per-option difference from the float32 worker
is at most 2 x (bf16 reference vs float32) + 0.01, and the top option matches
float32 wherever float32's top-two margin is at least 0.05.
"""
import json
import sys
import urllib.request
from pathlib import Path

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
url, inputs, parity = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])


def load(path):
    rows = [json.loads(l) for l in path.read_text().splitlines() if l]
    return {(r["case"], r["question"]): r["worker"] for r in rows}


fp32, bf16 = load(parity / "parity_float32.jsonl"), load(parity / "parity_bfloat16.jsonl")
diff = lambda a, b: max(abs(a[k] - b[k]) for k in a)
allowance = 2 * max(diff(bf16[k], fp32[k]) for k in fp32) + 0.01
worst, changed = 0.0, []
for case, body in json.loads(inputs.read_text()).items():
    req = urllib.request.Request(url + "/v1/systemone", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    answers = json.loads(OPENER.open(req, timeout=120).read())["answers"]
    for q, ans in answers.items():
        ref, got = fp32[(case, q)], ans["probabilities"]
        d = diff(got, ref)
        worst = max(worst, d)
        top = sorted(ref.values(), reverse=True)
        margin = top[0] - (top[1] if len(top) > 1 else 0.0)
        if margin >= 0.05 and max(ref, key=ref.get) != ans["choice"]:
            changed.append(f"{case}/{q}")
        print(f"{case + '/' + q:28s} |worker - fp32| {d:.4f}  choice {ans['choice']}")
ok = worst <= allowance and not changed
print(f"largest |worker - fp32| {worst:.4f}, allowance {allowance:.4f}, top-option changes {len(changed)} {changed}")
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
