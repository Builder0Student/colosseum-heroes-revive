"""Step 2 of 4: index the converted Unity project (textures, materials, shaders by name and GUID) into proj.json. Usage: python index_project.py <project>/Assets proj.json"""
import sys, os, re, glob, json, collections
P=sys.argv[1]
tex=collections.defaultdict(list); mats=collections.defaultdict(list); shaders={}
for meta in glob.glob(P+'/**/*.meta',recursive=True):
    a=meta[:-5]
    if os.path.isdir(a): continue
    g=re.search(r'^guid: (\w+)',open(meta,errors='replace').read(),re.M).group(1)
    ext=os.path.splitext(a)[1].lower(); rel=os.path.relpath(a,P)
    if ext in('.png','.jpg','.tga','.psd'):
        tex[os.path.splitext(os.path.basename(a))[0]].append({'rel':rel,'guid':g,'fid':2800000,'type':3})
    elif ext=='.asset':
        s=open(a,errors='replace').read(2000)
        if '--- !u!28 ' in s:
            n=re.search(r'm_Name: (.*)',s).group(1).strip()
            fid=re.search(r'--- !u!28 &(-?\d+)',s).group(1)
            tex[n].append({'rel':rel,'guid':g,'fid':int(fid),'type':2})
    elif ext=='.mat':
        s=open(a,errors='replace').read()
        n=re.search(r'm_Name: (.*)',s).group(1).strip()
        sh=re.search(r'm_Shader: (\{.*\})',s).group(1)
        mats[n].append({'rel':rel,'guid':g,'shader':sh,'empty':'m_TexEnvs: {}' in s or 'm_TexEnvs: []' in s})
    elif ext=='.shader':
        s=open(a,errors='replace').read(500)
        shaders[g]={'rel':rel,'name':re.search(r'Shader\s+"([^"]+)"',s).group(1) if re.search(r'Shader\s+"([^"]+)"',s) else None}
json.dump({'tex':tex,'mats':mats,'shaders':shaders},open(sys.argv[2],'w'),indent=1)
print('tex names',len(tex),'dups',[k for k,v in tex.items() if len(v)>1][:20])
print('mat names',len(mats),'dups',[k for k,v in mats.items() if len(v)>1][:30])
print('empty mats',sum(1 for v in mats.values() for m in v if m['empty']))
