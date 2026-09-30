"""Send one corpus to a worker and save (status, body) per request; or compare two saved runs."""
import json, sys, urllib.request, urllib.error
if sys.argv[1] == "compare":
    a, b = (json.load(open(p)) for p in sys.argv[2:4])
    same_ok = same_status = 0
    for name in a:
        sa, sb = a[name], b[name]
        if sa["status"] != sb["status"]:
            print("STATUS DIFF", name, sa["status"], sb["status"], sb["body"][:150]); continue
        same_status += 1
        if sa["status"] == 200:
            ja, jb = json.loads(sa["body"]), json.loads(sb["body"])
            if ja == jb: same_ok += 1
            else:
                pa = [p for q in ja["answers"].values() for p in q["probabilities"].values()]
                pb = [p for q in jb["answers"].values() for p in q["probabilities"].values()]
                print("ANSWER DIFF", name, "max |dp| =", max(abs(x - y) for x, y in zip(pa, pb)), "usage", ja["usage"] == jb["usage"])
    n200 = sum(1 for v in a.values() if v["status"] == 200)
    print(f"{same_status}/{len(a)} same status; {same_ok}/{n200} identical parsed 200 responses"); sys.exit(0)
url, inputs, out = sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3]
M = "cua-s1-4b-0.2"
def q(**kw):
    d = {"type": "choice", "instructions": "Pick.", "criteria": {"a": "A", "b": "B"}}; d.update(kw); return d
def req(state="Screen", questions=None, model=M):
    return json.dumps({"model": model, "state": state, "questions": questions or {"q": q()}}).encode()
corpus = {f"input:{k}": json.dumps(v, ensure_ascii=False).encode() for k, v in inputs.items()}
corpus.update({
  "dup_key": b'{"model": "cua-s1-4b-0.2", "state": {"x": 1, "x": 2}, "questions": {"q": {"type": "choice", "instructions": "I", "criteria": {"a": "A"}}}}',
  "nan": b'{"model": "cua-s1-4b-0.2", "state": NaN}', "inf": b'{"model": "cua-s1-4b-0.2", "state": {"x": 1e400}}',
  "bigint": b'{"model": "cua-s1-4b-0.2", "state": {"x": ' + b"9" * 5000 + b"}}",
  "surrogate": b'{"model": "cua-s1-4b-0.2", "state": "\\ud800"}', "deep": b"[" * 100000 + b"]" * 100000,
  "bad_utf8": b"\xff\xfe", "bom": b"\xef\xbb\xbf{}", "not_json": b"not json", "array": b"[1, 2]",
  "score": req(questions={"s": q(type="score", criteria=["l", "h"])}), "noul": req(questions={"n": q(type="noul")}),
  "rank": req(questions={"r": q(type="rank")}), "no_options": req(questions={"q": q(criteria={})}),
  "27_options": req(questions={"q": q(criteria={f"o{i}": "x" for i in range(27)})}),
  "26_options": req(questions={"q": q(criteria={f"o{i}": f"x{i}" for i in range(26)})}),
  "no_instructions": req(questions={"q": {"type": "choice", "criteria": {"a": "A"}}}),
  "num_label": req(questions={"q": q(criteria={"a": 1})}), "bool_label": req(questions={"q": q(criteria={"a": True})}),
  "empty_state": req(""), "empty_obj_state": req({}), "null_state": req(None), "num_state": req(3),
  "no_state": json.dumps({"model": M, "questions": {"q": q()}}).encode(),
  "wrong_model": req(model="english"), "no_questions": json.dumps({"model": M, "state": "S"}).encode(),
  "65_questions": req(questions={f"q{i}": q() for i in range(65)}), "question_not_obj": req(questions={"q": "x"}),
  "big_body": b" " * (4 << 20) + req(), "sa_keys": req(questions={"_sa": q(criteria={"_x": "A", "b": "B"})}),
  "null_goal": req(questions={"q": q(instructions=None)}), "null_label": req(questions={"q": q(criteria={"a": None, "b": "B"})}),
})
res = {}
for name, body in corpus.items():
    r = urllib.request.Request(url + "/v1/systemone", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=300) as resp: res[name] = {"status": resp.status, "body": resp.read().decode()}
    except urllib.error.HTTPError as e: res[name] = {"status": e.code, "body": e.read().decode()}
    except (urllib.error.URLError, ConnectionError) as e: res[name] = {"status": "reset", "body": str(e)}
json.dump(res, open(out, "w"), ensure_ascii=False, indent=0); print(len(res), "requests saved to", out)
