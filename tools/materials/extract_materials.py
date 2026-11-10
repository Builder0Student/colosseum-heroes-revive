"""Step 1 of 4: read every Material from the original Unity 3.4 data (assets/bin/Data of your own APK copy) with UnityPy and write origmats.json (shader, textures, floats, colors). Usage: python extract_materials.py <Data dir> origmats.json"""
import sys, os, UnityPy, json
D=sys.argv[1]; out=sys.argv[2]
files={}
def load(f):
    if f not in files:
        env=UnityPy.load(os.path.join(D,f)); sf=list(env.files.values())[0]
        files[f]=(env,sf,{o.path_id:o for o in env.objects})
    return files[f]
def ext_name(sf,fid):
    e=sf.externals[fid-1]
    g=e.guid
    gh=g.hex() if isinstance(g,(bytes,bytearray)) else str(g)
    return e.path, gh
names=[f for f in os.listdir(D) if os.path.isfile(os.path.join(D,f))]
res=[]
exts=set()
for f in sorted(names):
    try: env,sf,objs=load(f)
    except Exception: continue
    for o in objs.values():
        if o.type.name!='Material': continue
        t=o.read_typetree()
        def resolve(pp):
            fid,pid=pp['m_FileID'],pp['m_PathID']
            if pid==0: return None
            if fid==0: tgt=(f,pid)
            else:
                path,gh=ext_name(sf,fid); exts.add(path)
                base=os.path.basename(path)
                tgt=(base if base in names else path,pid)
            info={'file':tgt[0],'pid':tgt[1]}
            if tgt[0] in names:
                try:
                    _,_,o2=load(tgt[0]); ob=o2.get(tgt[1])
                    if ob: 
                        info['type']=ob.type.name
                        try: info['name']=ob.read_typetree().get('m_Name')
                        except Exception as e: info['err']=repr(e)[:80]
                except Exception as e: info['err']=repr(e)[:80]
            return info
        sp=t['m_SavedProperties']
        res.append({'srcfile':f,'pid':o.path_id,'name':t['m_Name'],'shader':resolve(t['m_Shader']),
            'tex':[[k['name'],resolve(v['m_Texture']),v['m_Scale'],v['m_Offset']] for k,v in sp['m_TexEnvs']],
            'floats':[[k['name'],v] for k,v in sp['m_Floats']],
            'colors':[[k['name'],v] for k,v in sp['m_Colors']]})
json.dump(res,open(out,'w'),indent=1,default=str)
print(len(res)); print(sorted(exts)[:20])
