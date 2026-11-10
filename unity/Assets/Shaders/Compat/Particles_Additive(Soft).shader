Shader "Compat/Particles/Additive (Soft)" {
Properties {
    _TintColor ("Tint Color", Color) = (0.5,0.5,0.5,0.5)
    _MainTex ("Particle Texture", 2D) = "white" {}
    _InvFade ("Soft Particles Factor", Range(0.01,3.0)) = 1.0
}
SubShader {
    Tags { "Queue"="Transparent" "IgnoreProjector"="True" "RenderType"="Transparent" }
    Blend One OneMinusSrcColor
    Cull Off Lighting Off ZWrite Off Fog { Mode Off }
    Pass {
        CGPROGRAM
        #pragma vertex vert
        #pragma fragment frag
        #include "UnityCG.cginc"
        sampler2D _MainTex; float4 _MainTex_ST; fixed4 _TintColor;
        struct appdata { float4 vertex : POSITION; fixed4 color : COLOR; float2 texcoord : TEXCOORD0; };
        struct v2f { float4 pos : SV_POSITION; fixed4 color : COLOR; float2 uv : TEXCOORD0; };
        v2f vert (appdata v) { v2f o; o.pos = UnityObjectToClipPos(v.vertex); o.color = v.color; o.uv = TRANSFORM_TEX(v.texcoord, _MainTex); return o; }
        fixed4 frag (v2f i) : SV_Target { fixed4 c = i.color * tex2D(_MainTex, i.uv); c.rgb *= c.a; return c; }
        ENDCG
    }
}
}
