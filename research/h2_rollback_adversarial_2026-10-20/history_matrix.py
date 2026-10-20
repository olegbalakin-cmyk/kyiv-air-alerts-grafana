"""H01-H12 canonical migration validity using actual PostgreSQL constraints."""
from harness import *

def run():
    def valid(id,ops):
        d=new(id.lower(),stage="raw")
        for tag,identity,city,parent_tag in ops:
            parent=ids.get(parent_tag) if parent_tag else None
            uid=put(d,tag,identity,city,parent)
            ids[tag]=uid
        prior=fingerprint(d)
        state=ns.run(d,ns.REF/"001_revision_invariants.sql",role="h2_migrator_test")
        step("H",id,"actual_001",d,"001","00000",state,prior,fingerprint(d))
        requires(len(heads(d))==(len(set((i,c) for _,i,c,_ in ops))),"unexpected number of tips")
    record("H","H01",lambda:valid("H01",[]))
    ids={}
    record("H","H02",lambda:valid("H02",[("h02",1,"kyiv",None)]))
    ids={}
    record("H","H03",lambda:valid("H03",[("h03a",1,"kyiv",None),("h03b",1,"kyiv","h03a"),("h03c",1,"kyiv","h03b")]))
    def preflight_failure(id,ops,msg):
        d=new(id.lower(),stage="raw"); p={}
        for tag,i,city,parent in ops:
            p[tag]=put(d,tag,i,city,p.get(parent))
        before=fingerprint(d)
        st=ns.run(d,ns.REF/"001_revision_invariants.sql",role="h2_migrator_test",ok=False)
        step("H",id,msg,d,"001","23514",st,before,fingerprint(d))
        requires(fingerprint(d)==before,"migration side effects despite failure")
    record("H","H04",lambda:preflight_failure("H04",[("a",1,"kyiv",None),("b",1,"kyiv",None)],"multiple roots"))
    record("H","H05",lambda:preflight_failure("H05",[("a",1,"kyiv",None),("b",1,"kyiv","a"),("c",1,"kyiv","a")],"duplicate successor"))
    def rejected_fk(id):
        d=new(id.lower(),stage="raw")
        st,before,after=invalid_put(d,id,1,"kyiv",str(uuid.uuid4()))
        step("H",id,"foreign_key",d,"INSERT","23503",st,before,after)
        requires(before==after,"FK refusal changed history")
    record("H","H06",lambda:rejected_fk("H06"))
    record("H","H07",lambda:preflight_failure("H07",[("a",1,"kyiv",None),("b",2,"kyiv","a")],"cross episode"))
    record("H","H08",lambda:preflight_failure("H08",[("a",1,"kyiv",None),("b",1,"kharkiv","a")],"cross city identity"))
    def cyclic():
        d=new("h09",stage="raw")
        # use a deferred? The historical FK is immediate, so a cycle cannot be inserted
        # without updating existing rows. Owner's UPDATE is pre-migration possible.
        a=put(d,"h09a");bb=put(d,"h09b",parent=a)
        query(d,"UPDATE public.attack_event_classifications SET supersedes_classification_uid=%s WHERE classification_uid=%s",(bb,a))
        before=fingerprint(d)
        step("H","H09","cyclic_migration",d,"001","23514",
             ns.run(d,ns.REF/"001_revision_invariants.sql",role="h2_migrator_test",ok=False),before,fingerprint(d))
        requires(before==fingerprint(d),"mutated cyclic history")
    record("H","H09",cyclic)
    record("H","H10",lambda:preflight_failure("H10",[("a",1,"kyiv",None),("b",1,"kyiv","a"),("c",1,"kyiv","a")],"two terminal tips"))
    def registry_mismatch():
        d=new("h11")
        a=put(d,"h11a");b=put(d,"h11b",parent=a)
        # Existing FK permits registry to point at an old revision.
        query(d,"UPDATE public.h2_classification_heads SET tip_classification_uid=%s",(a,))
        before=fingerprint(d)
        # Genuine migration replay rejects existing tables/indexes, leaving corrupt head intact.
        st=ns.run(d,ns.REF/"001_revision_invariants.sql",role="h2_migrator_test",ok=False)
        step("H","H11","corrupt_head_and_reapply",d,"001",{"42P07","42P07"},st,before,fingerprint(d))
        requires(before==fingerprint(d),"migration wrote to inconsistent registry")
        ALL["limitations"].append("H11 actual canonical migration does not perform a head-to-history consistency validation on an already-migrated DB; reapplication fails because objects exist")
        return "PARTIAL"
    record("H","H11",registry_mismatch)
    def repeated():
        d=new("h12")
        before=fingerprint(d)
        st=ns.run(d,ns.REF/"001_revision_invariants.sql",role="h2_migrator_test",ok=False)
        step("H","H12","second_001",d,"001",{"42P07","42710"},st,before,fingerprint(d))
        requires(before==fingerprint(d),"replay mutated")
    record("H","H12",repeated)
if __name__=="__main__":run()
