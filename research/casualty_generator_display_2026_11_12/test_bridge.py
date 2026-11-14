#!/usr/bin/env python3
"""Assertions against generated Work A output (not a UI fixture)."""
import json,sys
from pathlib import Path
qualified,report,probe=[json.loads(Path(p).read_text()) for p in sys.argv[1:]]
rows=qualified["casualties_by_city"]["zaporizhzhia"]["monthly"]
october=[r for r in rows if r["month"]=="2026-10"]
assert len(october)==1
r=october[0]
assert (r["coverage_status"],r["confirmed_minimum"],r["deaths"],r["complete_total"])==("INCOMPLETE",23,None,None)
assert any(x["month"]=="2026-10" and x["deaths"]==23 for x in probe["isolated_dashboard_patch"]["casualties_by_city"]["zaporizhzhia"]["monthly"])
assert report["publication_allowed"] is False
assert len(qualified["cities"])==23 and len(qualified["casualties_by_city"])==23
assert all(other.get("coverage_status")!="COMPLETE" for other in rows)
print("REAL_GENERATOR_COVERAGE_CONTRACT_PASS")
