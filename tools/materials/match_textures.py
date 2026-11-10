"""Step 3 of 4: match each original texture reference to a project texture by name and pixel size; writes texmap.json. Usage: python match_textures.py <Data dir> <project>/Assets   (run in the folder holding origmats.json and proj.json)"""
import sys, os, re, json, struct, UnityPy
D=sys.argv[1]; P=sys.argv[2]
r=json.load(open('origmats.json')); p=json.load(open('proj.json'))
need={}
for m in r:
    for t in m['tex']:
        if t[1]: need[(t[1]['file'],t[1]['pid'])]=t[1]['name']
envs={}
def dims(f,pid):
    if f not in envs: envs[f]=UnityPy.load(os.path.join(D,f) if os.path.exists(os.path.join(D,f)) else f)
    for o in envs[f].objects:
        if o.path_id==pid:
            t=o.read_typetree(); return t['m_Width'],t['m_Height']
def pdims(e):
    a=os.path.join(P,e['rel'])
    if a.endswith('.png'):
        d=open(a,'rb').read(24); return struct.unpack('>II',d[16:24])
    s=open(a,errors='replace').read(3000)
    return int(re.search(r'm_Width: (\d+)',s).group(1)),int(re.search(r'm_Height: (\d+)',s).group(1))
out={}
for (f,pid),n in sorted(need.items()):
    try: od=dims(f,pid)
    except Exception as e: od=('ERR',repr(e)[:60])
    cands=p['tex'].get(n,[])
    cd=[(c['rel'],pdims(c)) for c in cands]
    ok=[c for c,(rel,d) in zip(cands,cd) if tuple(d)==tuple(od)] if isinstance(od,tuple) and od[0]!='ERR' else []
    out[f+'|'+str(pid)]={'name':n,'orig':od,'cands':cd,'pick':ok[0] if len(ok)==1 else None}
    print(n,f[:12],pid,od,cd,'->',ok[0]['rel'] if len(ok)==1 else ('AMBIG' if ok else 'NONE'))
json.dump(out,open('texmap.json','w'),indent=1)
