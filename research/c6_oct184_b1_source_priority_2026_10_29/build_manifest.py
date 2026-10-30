from pathlib import Path
import hashlib, json
root=Path(__file__).parent
items=[]
for p in sorted(root.iterdir()):
    if p.is_file() and p.name != 'sha256_manifest.json':
        b=p.read_bytes()
        items.append({'path':p.name,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)})
(root/'sha256_manifest.json').write_text(json.dumps({'schema_version':'c6-b1-sha256-manifest-v1','hash_scope':'local worktree files, not a Git certification','files':items},indent=2)+'\n')
