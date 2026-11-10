"""Restore shaders for the recovered project.

* The game's own fixed-function shaders: write the original Unity 3.4 ShaderLab source into AssetRipper's
  dummy .shader files (same GUIDs, so materials keep pointing at them).
* Built-in Unity 3.4 lit/particle/text shaders (referenced via unreliable built-in fileIDs): write explicit
  replacement shaders under Assets/Shaders/Compat and point the materials at them.
Usage: fix_shaders.py <converted Data dir> <InfoJson 3.5.0.json> <Assets dir>
"""
import sys, os, re, struct, collections, hashlib
sys.path.insert(0, os.path.dirname(__file__))
import sf8, tt

data, tree, assets = sys.argv[1:4]
T = tt.load_trees(tree)
objs, ext = {}, {}
for f in sf8.data_files(data):
    s = sf8.SF8(os.path.join(data, f))
    b, p = s.raw, s.meta_tail_off
    n, = struct.unpack_from("<i", b, p); p += 4
    lst = []
    for _ in range(n):
        e = b.index(b"\0", p); p = e + 1; p += 20
        e = b.index(b"\0", p); lst.append(os.path.basename(b[p:e].decode())); p = e + 1
    ext[f] = lst
    for o in s.objects:
        objs[(f, o.path_id)] = o


def rd(k):
    o = objs[k]
    return tt.read(T[o.class_id], o.data)[0]


shader_src = {}
for k, o in objs.items():
    if o.class_id == 48:
        sc = rd(k)["m_Script"]
        m = re.search(r'Shader\s+"([^"]+)"', sc)
        if m:
            shader_src[k] = (m.group(1), sc)

mat_shader = {}   # material name -> original shader name
for k, o in objs.items():
    if o.class_id == 21:
        d = rd(k)
        sp = d["m_Shader"]
        tgt = (k[0] if sp["m_FileID"] == 0 else ext[k[0]][sp["m_FileID"] - 1], sp["m_PathID"])
        if tgt in shader_src:
            mat_shader.setdefault(d["m_Name"], set()).add((shader_src[tgt][0], tgt))

# ---- replacement shaders for Unity 3.4 built-ins (scene has no lights and white ambient in the original) ----
LIT = r'''Shader "{name}" {{
Properties {{
    _Color ("Main Color", Color) = (1,1,1,1)
    _MainTex ("Base (RGB){alphaname}", 2D) = "white" {{}}{cutprop}
}}
SubShader {{
    Tags {{ {tags} }}
    LOD 100
    {state}
    Pass {{
        CGPROGRAM
        #pragma vertex vert
        #pragma fragment frag
        #include "UnityCG.cginc"
        sampler2D _MainTex; float4 _MainTex_ST; fixed4 _Color;{cutvar}
        struct v2f {{ float4 pos : SV_POSITION; float2 uv : TEXCOORD0; }};
        v2f vert (appdata_base v) {{ v2f o; o.pos = UnityObjectToClipPos(v.vertex); o.uv = TRANSFORM_TEX(v.texcoord, _MainTex); return o; }}
        fixed4 frag (v2f i) : SV_Target {{
            fixed4 c = tex2D(_MainTex, i.uv) * _Color;
            // Unity 3.4 original: lit by ambient only (no lights in the game), ambient = RenderSettings.ambientLight
            return c;
        }}
        ENDCG
    }}
}}
}}
'''

PARTICLE = r'''Shader "{name}" {{
Properties {{
    _TintColor ("Tint Color", Color) = (0.5,0.5,0.5,0.5)
    _MainTex ("Particle Texture", 2D) = "white" {{}}
    _InvFade ("Soft Particles Factor", Range(0.01,3.0)) = 1.0
}}
SubShader {{
    Tags {{ "Queue"="Transparent" "IgnoreProjector"="True" "RenderType"="Transparent" }}
    Blend {blend}
    Cull Off Lighting Off ZWrite Off Fog {{ Mode Off }}
    Pass {{
        CGPROGRAM
        #pragma vertex vert
        #pragma fragment frag
        #include "UnityCG.cginc"
        sampler2D _MainTex; float4 _MainTex_ST; fixed4 _TintColor;
        struct appdata {{ float4 vertex : POSITION; fixed4 color : COLOR; float2 texcoord : TEXCOORD0; }};
        struct v2f {{ float4 pos : SV_POSITION; fixed4 color : COLOR; float2 uv : TEXCOORD0; }};
        v2f vert (appdata v) {{ v2f o; o.pos = UnityObjectToClipPos(v.vertex); o.color = v.color; o.uv = TRANSFORM_TEX(v.texcoord, _MainTex); return o; }}
        fixed4 frag (v2f i) : SV_Target {{ {frag} }}
        ENDCG
    }}
}}
}}
'''

TEXT = r'''Shader "Compat/GUI/Text Shader" {
Properties {
    _MainTex ("Font Texture", 2D) = "white" {}
    _Color ("Text Color", Color) = (1,1,1,1)
}
SubShader {
    Tags { "Queue"="Transparent" "IgnoreProjector"="True" "RenderType"="Transparent" "PreviewType"="Plane" }
    Lighting Off Cull Off ZTest Always ZWrite Off Fog { Mode Off }
    Blend SrcAlpha OneMinusSrcAlpha
    Pass {
        CGPROGRAM
        #pragma vertex vert
        #pragma fragment frag
        #include "UnityCG.cginc"
        sampler2D _MainTex; float4 _MainTex_ST; fixed4 _Color;
        struct appdata { float4 vertex : POSITION; fixed4 color : COLOR; float2 texcoord : TEXCOORD0; };
        struct v2f { float4 pos : SV_POSITION; fixed4 color : COLOR; float2 uv : TEXCOORD0; };
        v2f vert (appdata v) { v2f o; o.pos = UnityObjectToClipPos(v.vertex); o.color = v.color * _Color; o.uv = TRANSFORM_TEX(v.texcoord, _MainTex); return o; }
        fixed4 frag (v2f i) : SV_Target { fixed4 c = i.color; c.a *= tex2D(_MainTex, i.uv).a; return c; }
        ENDCG
    }
}
}
'''

BUILTIN = {
    "Diffuse": ("Compat/Diffuse", LIT.format(name="Compat/Diffuse", alphaname="", cutprop="", cutvar="", cutclip="",
                tags='"RenderType"="Opaque"', state="")),
    "Transparent/Diffuse": ("Compat/Transparent/Diffuse", LIT.format(
        name="Compat/Transparent/Diffuse", alphaname=" Trans (A)", cutprop="", cutvar="", cutclip="",
        tags='"Queue"="Transparent" "IgnoreProjector"="True" "RenderType"="Transparent"',
        state="ZWrite Off Blend SrcAlpha OneMinusSrcAlpha")),
    "Transparent/Cutout/Diffuse": ("Compat/Transparent/Cutout/Diffuse", LIT.format(
        name="Compat/Transparent/Cutout/Diffuse", alphaname=" Trans (A)",
        cutprop='\n    _Cutoff ("Alpha cutoff", Range(0,1)) = 0.5', cutvar=" fixed _Cutoff;", cutclip="\n            clip(c.a - _Cutoff);",
        tags='"Queue"="AlphaTest" "IgnoreProjector"="True" "RenderType"="TransparentCutout"', state="")),
    "Particles/Alpha Blended": ("Compat/Particles/Alpha Blended", PARTICLE.format(
        name="Compat/Particles/Alpha Blended", blend="SrcAlpha OneMinusSrcAlpha",
        frag="return 2.0f * i.color * _TintColor * tex2D(_MainTex, i.uv);")),
    "Particles/Additive (Soft)": ("Compat/Particles/Additive (Soft)", PARTICLE.format(
        name="Compat/Particles/Additive (Soft)", blend="One OneMinusSrcColor",
        frag="fixed4 c = i.color * tex2D(_MainTex, i.uv); c.rgb *= c.a; return c;")),
    "Particles/Alpha Blended Premultiply": ("Compat/Particles/Alpha Blended Premultiply", PARTICLE.format(
        name="Compat/Particles/Alpha Blended Premultiply", blend="One OneMinusSrcAlpha",
        frag="return i.color * tex2D(_MainTex, i.uv) * i.color.a;")),
    "GUI/Text Shader": ("Compat/GUI/Text Shader", TEXT),
}

META = "fileFormatVersion: 2\nguid: {g}\nShaderImporter:\n  externalObjects: {{}}\n  defaultTextures: []\n  nonModifiableTextures: []\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n"


def guid_for(name):
    return hashlib.md5(("colosseum-compat-shader:" + name).encode()).hexdigest()


stats = collections.Counter()
comp_dir = os.path.join(assets, "Shaders", "Compat")
os.makedirs(comp_dir, exist_ok=True)
builtin_guid = {}
for orig, (newname, src) in BUILTIN.items():
    fn = newname.split("/", 1)[1].replace("/", "_").replace(" ", "") + ".shader"
    g = guid_for(newname)
    open(os.path.join(comp_dir, fn), "w").write(src)
    open(os.path.join(comp_dir, fn + ".meta"), "w").write(META.format(g=g))
    builtin_guid[orig] = g
for d in (os.path.join(assets, "Shaders"),):
    open(d + ".meta", "w").write(f"fileFormatVersion: 2\nguid: {guid_for('dir:Shaders')}\nfolderAsset: yes\nDefaultImporter:\n  externalObjects: {{}}\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n")
open(comp_dir + ".meta", "w").write(f"fileFormatVersion: 2\nguid: {guid_for('dir:Shaders/Compat')}\nfolderAsset: yes\nDefaultImporter:\n  externalObjects: {{}}\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n")

# map dummy shader files (by GUID) -> original shader via the materials that use them
dummy_by_guid = {}
for fn in os.listdir(os.path.join(assets, "Shader")):
    if fn.endswith(".shader.meta"):
        g = re.search(r"^guid: (\w+)", open(os.path.join(assets, "Shader", fn)).read(), re.M).group(1)
        dummy_by_guid[g] = os.path.join(assets, "Shader", fn[:-5])

restored = {}
for dp, _, fs in os.walk(assets):
    for fn in fs:
        if not fn.endswith(".mat"):
            continue
        path = os.path.join(dp, fn)
        text = open(path).read()
        name = re.search(r"m_Name: ?(.*)", text).group(1).strip()
        m = re.search(r"m_Shader: \{fileID: (\d+), guid: (\w+), type: (\d)\}", text)
        origs = mat_shader.get(name, set())
        orig_names = {o[0] for o in origs}
        if len(orig_names) != 1:
            stats[f"unmapped material ({len(orig_names)} candidates)"] += 1
            continue
        orig = orig_names.pop()
        if orig in BUILTIN:
            text = text[:m.start()] + f"m_Shader: {{fileID: 4800000, guid: {builtin_guid[orig]}, type: 3}}" + text[m.end():]
            open(path, "w").write(text)
            stats[f"material -> {BUILTIN[orig][0]}"] += 1
        elif m.group(2) in dummy_by_guid:
            src = [shader_src[k][1] for k in shader_src if shader_src[k][0] == orig][0]
            if dummy_by_guid[m.group(2)] not in restored:
                open(dummy_by_guid[m.group(2)], "w").write(src)
                restored[dummy_by_guid[m.group(2)]] = orig
            stats["material -> restored game shader"] += 1
        else:
            stats[f"other: {orig}"] += 1
for p, o in restored.items():
    print(f"restored {os.path.basename(p)} <- '{o}'")
print(dict(stats))
