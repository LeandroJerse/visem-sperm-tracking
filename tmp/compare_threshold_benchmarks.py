import csv,json,sys,hashlib
from pathlib import Path

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p): return json.loads(p.read_text(encoding="utf-8"))
old,new,out=map(Path,sys.argv[1:])
a,b=load(old),load(new)
assert a["status"]==b["status"]=="complete"
assert a["summary"]["plan_hash"]==b["summary"]["plan_hash"]
assert a["summary"]["sample_hash"]==b["summary"]["sample_hash"]
def children(m):
 return {load(Path(r["path"]))["summary"]["configuration_id"]:Path(r["path"]) for r in m["candidate_manifests"]}
x,y=children(a),children(b)
assert set(x)==set(y) and len(x)==171
checks=[]
for key in sorted(x):
 pa,pb=x[key].parent,y[key].parent
 raw_equal=sha(pa/"detections.csv")==sha(pb/"detections.csv")
 assert raw_equal,key
 def rows(p):
  with p.open(encoding="utf-8",newline="") as f:
   return [{k:v for k,v in row.items() if k!="detection_ms"} for row in csv.DictReader(f)]
 ra,rb=rows(pa/"frame_metrics.csv"),rows(pb/"frame_metrics.csv")
 assert ra==rb and len(ra)==12,key
 checks.append({"configuration_id":key,"detections_sha256":sha(pa/"detections.csv"),"frame_metrics_equal_except_detection_ms":True})
report={"status":"passed","old_manifest":str(old),"old_sha256":sha(old),"new_manifest":str(new),"new_sha256":sha(new),"plan_hash":b["summary"]["plan_hash"],"sample_hash":b["summary"]["sample_hash"],"candidates":171,"frame_evaluations":2052,"raw_predictions_and_full_gt_csv_identical":True,"checks":checks}
with out.open("x",encoding="utf-8") as f:json.dump(report,f,ensure_ascii=False,indent=2)
print(json.dumps({k:v for k,v in report.items() if k!="checks"},ensure_ascii=False))
