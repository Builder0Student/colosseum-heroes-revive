"""Step 4 of 4: rewrite the empty m_SavedProperties of every .mat in the project with the original textures, floats and colors; writes the new files to <out dir>. Usage: python write_materials.py <project>/Assets <out dir>   (run in the folder holding the three JSON files)"""
import sys, os, re, json, struct, collections
P=sys.argv[1]; OUT=sys.argv[2]
r=json.load(open('origmats.json')); p=json.load(open('proj.json')); tm=json.load(open('texmap.json'))
def fmt(v):
    f32=struct.unpack('<f',struct.pack('<f',v))[0]
    for pr in range(1,10):
        t='%.*g'%(pr,v)
        if struct.unpack('<f',struct.pack('<f',float(t)))[0]==f32: break
    if 'e' in t: t=repr(float(t))
    return t
# project fonts
pfont={}
for rel in ['Font/MAILRAYS.asset','Resources/font/COASBL.asset','Resources/font/COASBL_1.asset','Resources/font/MAILRAYS_Small.asset','Resources/font/MAILRAYS_Small_1.asset']:
    s=open(os.path.join(P,rel)).read()
    n=re.search(r'm_Name: (.*)',s).group(1).strip()
    mg=re.search(r'm_DefaultMaterial: \{fileID: 2100000, guid: (\w+)',s).group(1)
    tg=re.search(r'm_Texture: \{fileID: 2800000, guid: (\w+), type: 3\}',s).group(1)
    pfont[n]={'mat':mg,'tex':tg}
guid2rel={}
for v in p['tex'].values():
    for e in v: guid2rel[e['guid']]=e
# orig fonts: file -> (fontname, matpid, texpid)
ofont={'21bd5c82650b60743a6e4852e171a1f0':('COASBL_1',1,2),'3453e770ac71be94d8fd8341f611ffa7':('MAILRAYS_Small_1',1,2),
 '39ee8b6e3fed4f34abf6b51701e8f258':('MAILRAYS_Small',1,2),'d80fdb533596c254aa3759f182cf1e98':('COASBL',1,2),'sharedassets0.assets':('MAILRAYS',8,11)}
fonttex={(f,v[2]):pfont[v[0]]['tex'] for f,v in ofont.items()}
fontmat_by_guid={pfont[v[0]]['mat']:(f,v[1]) for f,v in ofont.items()}
def pdims(rel):
    a=os.path.join(P,rel); d=open(a,'rb').read(24); return struct.unpack('>II',d[16:24])
skey=lambda m: (m['shader']['file'],m['shader']['pid']) if m['shader'] else None
# shader map from unique names
umap=collections.defaultdict(set)
pc=collections.Counter(m['name'] for m in r)
for n,v in p['mats'].items():
    if len(v)==1 and pc[n]==1:
        o=[m for m in r if m['name']==n][0]
        umap[skey(o)].add(v[0]['shader'])
print('shader map',{k:len(v) for k,v in umap.items()})
assert all(len(v)==1 for v in umap.values()), umap
smap={k:list(v)[0] for k,v in umap.items()}
def texref(t):
    if t is None: return '{fileID: 0}'
    key=(t['file'],t['pid'])
    if key in fonttex:
        g=fonttex[key]; e=guid2rel[g]
        od=tm[t['file']+'|'+str(t['pid'])]['orig']
        assert tuple(pdims(e['rel']))==tuple(od),(e,od)
        return '{fileID: 2800000, guid: %s, type: 3}'%g
    pk=tm[t['file']+'|'+str(t['pid'])]['pick']
    assert pk, t
    return '{fileID: %d, guid: %s, type: %d}'%(pk['fid'],pk['guid'],pk['type'])
report=[]; os.makedirs(OUT,exist_ok=True)
for n,v in p['mats'].items():
    for pm in v:
        if pm['guid'] in fontmat_by_guid:
            f,pid=fontmat_by_guid[pm['guid']]; o=[m for m in r if m['srcfile']==f and m['pid']==pid][0]; how='font'
        else:
            c=[m for m in r if m['name']==n]
            if len(c)>1: c=[m for m in c if smap.get(skey(m))==pm['shader']]; how='shader'
            else: how='name'
            assert len(c)==1,(n,pm,len(c)); o=c[0]
        sh=skey(o)
        if sh in smap and smap[sh]!=pm['shader']: print('SHADER MISMATCH',n,sh,pm['shader'])
        L=['  m_SavedProperties:','    serializedVersion: 3']
        if o['tex']:
            L.append('    m_TexEnvs:')
            for name,t,sc,of in o['tex']:
                L+=['    - %s:'%name,'        m_Texture: %s'%texref(t),'        m_Scale: {x: %s, y: %s}'%(fmt(sc['x']),fmt(sc['y'])),'        m_Offset: {x: %s, y: %s}'%(fmt(of['x']),fmt(of['y']))]
        else: L.append('    m_TexEnvs: []')
        if o['floats']:
            L.append('    m_Floats:'); L+=['    - %s: %s'%(k,fmt(x)) for k,x in o['floats']]
        else: L.append('    m_Floats: []')
        if o['colors']:
            L.append('    m_Colors:'); L+=['    - %s: {r: %s, g: %s, b: %s, a: %s}'%(k,fmt(c['r']),fmt(c['g']),fmt(c['b']),fmt(c['a'])) for k,c in o['colors']]
        else: L.append('    m_Colors: []')
        src=open(os.path.join(P,pm['rel']),newline='').read()
        nl='\r\n' if '\r\n' in src else '\n'
        i=src.index('  m_SavedProperties:')
        tail=src[i:]
        assert re.fullmatch(r'  m_SavedProperties:\r?\n    serializedVersion: 3\r?\n    m_TexEnvs: \{\}\r?\n    m_Floats: \{\}\r?\n    m_Colors: \{\}\r?\n?',tail),(pm['rel'],tail)
        new=src[:i]+nl.join(L)+nl
        dst=os.path.join(OUT,pm['rel']); os.makedirs(os.path.dirname(dst),exist_ok=True)
        open(dst,'w',newline='').write(new)
        report.append((pm['rel'],how,o['srcfile'][:12],o['pid'],[ (t[0],t[1]['name'] if t[1] else None) for t in o['tex']]))
json.dump(report,open('genreport.json','w'),indent=1)
print(len(report),'written'); print(collections.Counter(x[1] for x in report))
