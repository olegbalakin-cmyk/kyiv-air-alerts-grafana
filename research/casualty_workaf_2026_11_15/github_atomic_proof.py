"""Two simultaneous GitHub API create-ref attempts with one synthetic GO.

No publisher/media HTTP. GH REST API is the only network destination.
"""
import concurrent.futures
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"kyiv-air-alerts-grafana/scripts"))
import casualty_go_guard as go

HEAD=os.environ["GITHUB_SHA"]
TOKEN=os.environ["GITHUB_TOKEN"]
REPO=os.environ["GITHUB_REPOSITORY"]
ID="workaf-synthetic-"+HEAD[:24]
G={"owner_go_id":ID,"approved_head":HEAD,
   "allowed_urls":{"rss":["https://www.ukrinform.ua/rss/block-lastnews"],"article":[]},
   "rss_get_budget":1,"article_get_budget":0,
   "allowed_methods":["GET"],"expires_at":"2099-01-01T00:00:00Z"}
DIGEST=go.canonical_digest(G)

def attempt():
    try:
        lease=go.claim_grant(G,approved_digest=DIGEST,head=HEAD,
                             repo=REPO,token=TOKEN)
        return {"won":True,"ref":lease.spent_ref}
    except go.GoBlocked as exc:
        return {"won":False,"failure":str(exc)}

before=go.lookup_spent_ref(repo=REPO,token=TOKEN,owner_go_id=ID)
if before is None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:attempt(),range(2)))
    assert sum(bool(x["won"]) for x in results)==1,results
    mode="FIRST_CLAIM_ONE_WINNER"
else:
    assert before==HEAD
    results=[attempt(),attempt()]
    assert not any(x["won"] for x in results)
    mode="ALREADY_CLAIMED_RERUN_BLOCKED"
after=go.lookup_spent_ref(repo=REPO,token=TOKEN,owner_go_id=ID)
assert after==HEAD, "GH spent GO ref is not persisted"
assert not attempt()["won"], "rerun reused consumed GO"
out=Path(os.getenv("WORKAF_OUT","/tmp/workaf"))
out.mkdir(exist_ok=True,parents=True)
result={"mode":mode,"approved_head":HEAD,"owner_go_id":ID,
        "spent_ref":go.LEDGER_PREFIX+ID,"spent_sha_readback":after,
        "first_pair":results,"rerun_blocked":True,
        "media_gets":0,"article_gets":0,"wip_writes":0,
        "automatic_credits":0,"PROMOTE":"OFF"}
(out/"github_atomic_proof.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
print("WORKAF_GITHUB_ATOMIC",json.dumps(result,sort_keys=True))
