#!/usr/bin/env python3
import argparse, gzip, hashlib, json, re
from pathlib import Path
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

p=argparse.ArgumentParser()
p.add_argument("--root",required=True)
a=p.parse_args()
root=Path(a.root)
def sha(b): return hashlib.sha256(b).hexdigest()
def read(p):return (root/p).read_bytes()
def obj(p):return json.loads(read(p))
manifest=obj("metadata/manifest.json")
checks={}
for name,meta in manifest["members"].items():
    b=read(name)
    assert len(b)==meta["bytes"] and sha(b)==meta["sha256"],name
checks["manifest_members"]=len(manifest["members"])
src=obj("metadata/source_and_offline.json")
rss=read("raw/frozen_rss_gzip.bin")
h=read("raw/frozen_google_html_gzip.bin")
assert sha(rss)==src["source"]["rss_sha256"]=="0d615960a3af6e3d92ea1fb5dee7e8ed8049160e8924714d317e9e87ff3c21c5"
assert sha(h)==src["source"]["html_sha256"]=="9049878431e531ca05f12d16bcec21128aed73892fee3cbfeb314ceaba7992ac"
first=ET.fromstring(gzip.decompress(rss)).find("./channel/item")
item=src["item"]
assert first is not None
for key,tag in (("guid","guid"),("title","title"),("url","link"),("pubDate","pubDate"),("publisher","source")):
    assert (first.findtext(tag) or "").strip()==item[key]
assert first.find("source").get("url")==item["publisher_url"]=="https://www.bbc.com"
assert item["guid"]==urlsplit(item["url"]).path.rsplit("/",1)[-1]
assert b"data-n-a-sg" in gzip.decompress(h) or src["offline"]["unique_signed_pair_count"]==0
rpc=obj("metadata/google_rpc_observation.json")
adj=obj("derived/adjudication.json")
assert adj["item_guid"]==item["guid"]
assert adj["google_rpc_requests"] in (0,1)
assert adj["publisher_http_requests"]==adj["rss_refresh_requests"]==0
assert adj["publisher_article_body_requested"] is False
if rpc["attempted"]:
    assert rpc["attempts"]==1
    assert rpc["endpoint"]=="https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je"
    assert rpc["cookies_sent"] is False and rpc["redirect_following"] is False and rpc["retries"]==0
    req=read("raw/google_rpc_request_form.bin")
    raw=read("raw/google_rpc_response_entity.bin")
    assert sha(req)==rpc["request_body_sha256"] and len(req)==rpc["request_body_bytes"]
    assert sha(raw)==rpc["response_entity_sha256"] and len(raw)==rpc["response_entity_bytes"]
else:
    assert rpc["attempts"]==0
if adj["original_bbc_article_url"]:
    u=adj["original_bbc_article_url"]
    p=urlsplit(u)
    assert p.scheme=="https" and (p.hostname=="bbc.com" or p.hostname.endswith(".bbc.com") or p.hostname=="bbc.co.uk" or p.hostname.endswith(".bbc.co.uk"))
    assert len([x for x in p.path.split("/") if x])>=2
    assert rpc["http_status"]==200 and rpc["parsed_garturlres_candidates"]==[u]
    expected="PROVEN"
else:
    expected="PARTIAL" if any(x["validation_reject_reason"] is None for x in adj["candidate_urls"]) else "BLOCKED"
assert adj["verdict"]=="GOOGLE NEWS BBC ARTICLE URL RESOLUTION = "+expected
checks.update({"rss_sha256":sha(rss),"html_sha256":sha(h),"guid":item["guid"],"rpc_response_sha256":rpc.get("response_entity_sha256"),"rpc_count":rpc["attempts"],"publisher_requests":0,"verdict":adj["verdict"],"url":adj["original_bbc_article_url"],"manifest_sha256":sha(read("metadata/manifest.json"))})
print(json.dumps(checks,sort_keys=True,separators=(",",":"),ensure_ascii=False))
