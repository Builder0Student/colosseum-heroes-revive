#!/bin/bash
# Compile-check the recovered project's scripts the way Unity 2019.4 would: C# 7.3, .NET 4.x API.
# Usage: compile.sh <Assets dir> <engine refs dir> <out dir> [extra csc args]
set -u
A="$1"; R="$2"; OUT="$3"; shift 3
CSC="dotnet /usr/lib/dotnet/sdk/8.0.133/Roslyn/bincore/csc.dll"
API=/usr/lib/mono/4.7.2-api
BASE="-nologo -noconfig -nostdlib -langversion:7.3 -unsafe -nowarn:0618,0612,0414,0169,0649,0219,0108,0114,0162,0168,0429,1717,0109,0672 \
 -r:$API/mscorlib.dll -r:$API/System.dll -r:$API/System.Core.dll -r:$API/System.Xml.dll -r:$API/System.Data.dll \
 -r:$API/Facades/netstandard.dll -r:$API/Facades/System.Runtime.dll"
ENGINE=""
for d in "$R"/*.dll; do ENGINE="$ENGINE -r:$d"; done
mkdir -p "$OUT"
FP=$(find "$A/Plugins" -name '*.cs' | sort)
$CSC $BASE $ENGINE "$@" -target:library -out:"$OUT/Assembly-CSharp-firstpass.dll" $FP > "$OUT/firstpass.log" 2>&1
echo "firstpass: $(grep -c ' error ' "$OUT/firstpass.log") errors"
MAIN=$(find "$A" -name '*.cs' -not -path "$A/Plugins/*" -not -path '*/System.Runtime.CompilerServices.Unsafe/*' -not -path '*/Editor/*' | sort)
$CSC $BASE $ENGINE "$@" -r:"$OUT/Assembly-CSharp-firstpass.dll" -target:library -out:"$OUT/Assembly-CSharp.dll" $MAIN > "$OUT/main.log" 2>&1
echo "main: $(grep -c ' error ' "$OUT/main.log") errors"
