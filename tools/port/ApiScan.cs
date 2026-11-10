// Lists every member/type the given assemblies reference in external assemblies (UnityEngine, Boo.Lang, UnityScript.Lang),
// with use counts, as lines: <assembly>\t<declaring type>\t<member kind>\t<member name>\t<signature>\t<count>
using System;
using System.Collections.Generic;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

class ApiScan
{
    static void Main(string[] args)
    {
        var counts = new Dictionary<string, int>();
        Action<string> add = k => { counts[k] = counts.TryGetValue(k, out var c) ? c + 1 : 1; };
        foreach (var path in args)
        {
            var asm = AssemblyDefinition.ReadAssembly(path);
            foreach (var type in asm.MainModule.GetTypes())
            {
                if (type.BaseType != null) Note(type.BaseType, add, "base");
                foreach (var f in type.Fields) Note(f.FieldType, add, "fieldtype");
                foreach (var m in type.Methods)
                {
                    if (!m.HasBody) continue;
                    foreach (var ins in m.Body.Instructions)
                    {
                        if (ins.Operand is MemberReference mr)
                        {
                            var decl = mr.DeclaringType;
                            if (mr is TypeReference tr) { Note(tr, add, "typeref"); continue; }
                            if (decl == null) continue;
                            var scope = Scope(decl);
                            if (scope == null) continue;
                            string kind = mr is MethodReference ? "method" : mr is FieldReference ? "field" : "other";
                            string sig = mr is MethodReference mref ? "(" + string.Join(",", mref.Parameters.Select(p => p.ParameterType.Name)) + ")" : "";
                            add($"{scope}\t{Clean(decl)}\t{kind}\t{mr.Name}\t{sig}");
                        }
                    }
                }
            }
        }
        foreach (var kv in counts.OrderBy(k => k.Key)) Console.WriteLine(kv.Key + "\t" + kv.Value);
    }

    static string Clean(TypeReference t)
    {
        if (t is GenericInstanceType g) t = g.ElementType;
        return t.FullName;
    }

    static string Scope(TypeReference t)
    {
        if (t is TypeSpecification ts) t = ts.ElementType;
        var s = t.Scope?.Name ?? "";
        if (s.StartsWith("UnityEngine") || s.StartsWith("Boo.Lang") || s.StartsWith("UnityScript")) return s.Replace(".dll", "");
        return null;
    }

    static void Note(TypeReference t, Action<string> add, string kind)
    {
        var s = Scope(t);
        if (s != null) add($"{s}\t{Clean(t)}\t{kind}\t\t");
    }
}
