"""Execute independent R/H/C/D suites and preserve partial/failure reports."""
import importlib
import json
import traceback
from harness import *
import rollback_matrix
import history_matrix
import security_matrix
import acl_residual

def main():
    try:
        version=query("postgres","SHOW server_version")[0][0]
        ALL["pg_version"]=version
        if not version.startswith("18.6"):raise RuntimeError("PG18.6 required; found "+version)
        ns.roles()
        for name,suite in (("rollback",rollback_matrix),("history",history_matrix),
                           ("security",security_matrix),("acl",acl_residual)):
            print("BEGIN "+name,flush=True)
            try:suite.run()
            except Exception as exc:
                ALL["errors"].append({"section":name,"id":"UNHANDLED","error":repr(exc),
                                      "trace":traceback.format_exc()[-2200:]})
        required={"R":set("R%02d"%x for x in range(1,17)),
                  "H":set("H%02d"%x for x in range(1,13)),
                  "C":set("C%d"%x for x in range(1,9)),
                  "D":set("D%02d"%x for x in range(1,5))}
        for group,ids in required.items():
            got={x["id"] for x in ALL["records"] if x["section"]==group}
            missing=sorted(ids-got)
            if missing:ALL["errors"].append({"section":group,"id":"MISSING","missing":missing})
        ALL["gates"]={
          "H2_ROLLBACK_CONCURRENT_WRITER_SERIALIZATION":next((x["status"] for x in ALL["records"] if x["id"]=="R03"),"BLOCKED"),
          "H2_MIGRATION_INVALID_HISTORY_MATRIX":"PASS" if all(x["status"]=="PASS" for x in ALL["records"] if x["section"]=="H") and required["H"] <= {x["id"] for x in ALL["records"]} else "PARTIAL",
          "H2_SECURITY_DEFINER_ADVERSARIAL_CLOSURE":"PASS" if all(x["status"]=="PASS" for x in ALL["records"] if x["section"]=="C") and required["C"] <= {x["id"] for x in ALL["records"]} else "PARTIAL",
          "H2_ACL_RAW_CATALOG_EQUIVALENCE":"PARTIAL",
          "H2_FULL_SCHEMA_ACL_OWNERSHIP_ROLLBACK":"PARTIAL",
          "H2_READONLY_NEON_PREFLIGHT_READINESS":"BLOCKED",
          "H2_DISPOSABLE_NEON_TEST_READINESS":"BLOCKED"}
    finally:close()

if __name__=="__main__":main()
