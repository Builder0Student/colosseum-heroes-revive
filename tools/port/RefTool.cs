// Edit a reference assembly: query, remove members/types, and add stub members, to approximate the
// Unity 2019.4 API surface on top of the Unity 3.4 UnityEngine.dll for compile-checking.
// Usage: RefTool.exe <in.dll> <out.dll> <spec file>
// Spec lines:  has Type[::member]   |  rm Type::member  |  rm Type  |
//              prop Type::name:TypeName[:static][:get][:set]  |  method Type::name:ReturnType:static|inst:ParamType,...
//              type Namespace.Name:enum:A,B,C  |  type Namespace.Name:class
using System;
using System.IO;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

class RefTool
{
    static ModuleDefinition M;

    static TypeReference T(string name)
    {
        switch (name)
        {
            case "void": return M.TypeSystem.Void;
            case "bool": return M.TypeSystem.Boolean;
            case "int": return M.TypeSystem.Int32;
            case "float": return M.TypeSystem.Single;
            case "string": return M.TypeSystem.String;
            case "object": return M.TypeSystem.Object;
        }
        var t = M.GetType(name);
        if (t == null) throw new Exception("unknown type " + name);
        return t;
    }

    static void Stub(MethodDefinition m)
    {
        var il = m.Body.GetILProcessor();
        il.Append(il.Create(OpCodes.Ldnull));
        il.Append(il.Create(OpCodes.Throw));
    }

    // Reference-only output: stub every body and drop members whose signatures use types that no longer exist.
    static void Sanitize()
    {
        var live = new System.Collections.Generic.HashSet<string>(M.GetTypes().Select(t => t.FullName));
        Func<TypeReference, bool> dead = null;
        dead = tr =>
        {
            if (tr == null) return false;
            if (tr is GenericInstanceType git && git.GenericArguments.Any(x => dead(x))) return true;
            while (tr is TypeSpecification ts) tr = ts.ElementType;
            if (tr is GenericParameter) return false;
            if (tr is TypeDefinition td) return td.Module == null || (td.DeclaringType != null && dead(td.DeclaringType));
            return (tr.Scope == M || tr.Scope == null) && tr.Namespace.StartsWith("UnityEngine") && !live.Contains(tr.FullName);
        };
        foreach (var t in M.GetTypes().ToList())
        {
            foreach (var m in t.Methods.ToList())
            {
                if (dead(m.ReturnType) || m.Parameters.Any(p => dead(p.ParameterType))) { t.Methods.Remove(m); continue; }
                if (m.HasBody)
                {
                    m.Body = new MethodBody(m);
                    Stub(m);
                }
            }
            foreach (var p in t.Properties.ToList())
                if (dead(p.PropertyType) || (p.GetMethod != null && !t.Methods.Contains(p.GetMethod)) || (p.SetMethod != null && !t.Methods.Contains(p.SetMethod)))
                    t.Properties.Remove(p);
            foreach (var f in t.Fields.ToList()) if (dead(f.FieldType)) t.Fields.Remove(f);
            foreach (var e in t.Events.ToList()) if (dead(e.EventType)) t.Events.Remove(e);
            foreach (var n in t.NestedTypes.ToList()) if (!live.Contains(n.FullName)) t.NestedTypes.Remove(n);
            if (t.BaseType != null && dead(t.BaseType)) t.BaseType = M.TypeSystem.Object;
            foreach (var i in t.Interfaces.ToList()) if (dead(i)) t.Interfaces.Remove(i);
            foreach (var ca in t.CustomAttributes.ToList()) if (dead(ca.AttributeType)) t.CustomAttributes.Remove(ca);
            foreach (var m in t.Methods) foreach (var ca in m.CustomAttributes.ToList()) if (dead(ca.AttributeType)) m.CustomAttributes.Remove(ca);
            foreach (var m in t.Methods) foreach (var gp in m.GenericParameters) foreach (var c in gp.Constraints.ToList()) if (dead(c)) gp.Constraints.Remove(c);
        }
    }

    static void Main(string[] a)
    {
        var asm = AssemblyDefinition.ReadAssembly(a[0]);
        M = asm.MainModule;
        foreach (var raw in File.ReadAllLines(a[2]))
        {
            var line = raw.Trim();
            if (line.Length == 0 || line.StartsWith("#")) continue;
            var cmd = line.Split(new[] { ' ' }, 2);
            var arg = cmd[1];
            if (cmd[0] == "has")
            {
                var parts = arg.Split(new[] { "::" }, StringSplitOptions.None);
                var t = M.GetType(parts[0]);
                bool ok = t != null && (parts.Length == 1 || t.Methods.Any(x => x.Name == parts[1] || x.Name == "get_" + parts[1] || x.Name == "set_" + parts[1]) || t.Fields.Any(x => x.Name == parts[1]));
                Console.WriteLine((ok ? "yes " : "NO  ") + arg);
            }
            else if (cmd[0] == "rm")
            {
                var parts = arg.Split(new[] { "::" }, StringSplitOptions.None);
                var t = M.GetType(parts[0]);
                if (t == null) { Console.WriteLine("rm: no type " + parts[0]); continue; }
                if (parts.Length == 1) { M.Types.Remove(t); continue; }
                foreach (var p in t.Properties.Where(x => x.Name == parts[1]).ToList()) t.Properties.Remove(p);
                foreach (var m in t.Methods.Where(x => x.Name == parts[1] || x.Name == "get_" + parts[1] || x.Name == "set_" + parts[1]).ToList()) t.Methods.Remove(m);
                foreach (var f in t.Fields.Where(x => x.Name == parts[1]).ToList()) t.Fields.Remove(f);
            }
            else if (cmd[0] == "prop")
            {
                var head = arg.Split(new[] { "::" }, 2, StringSplitOptions.None);
                var rest = head[1].Split(':');
                var tn = new[] { head[0], rest[0] };
                var p = rest;
                var t = M.GetType(tn[0]); var pt = T(p[1]);
                bool isStatic = p.Contains("static");
                var attrs = MethodAttributes.Public | MethodAttributes.HideBySig | MethodAttributes.SpecialName | (isStatic ? MethodAttributes.Static : 0);
                var prop = new PropertyDefinition(tn[1], PropertyAttributes.None, pt);
                if (p.Contains("get")) { var g = new MethodDefinition("get_" + tn[1], attrs, pt); Stub(g); t.Methods.Add(g); prop.GetMethod = g; }
                if (p.Contains("set")) { var s = new MethodDefinition("set_" + tn[1], attrs, M.TypeSystem.Void); s.Parameters.Add(new ParameterDefinition("value", ParameterAttributes.None, pt)); Stub(s); t.Methods.Add(s); prop.SetMethod = s; }
                t.Properties.Add(prop);
            }
            else if (cmd[0] == "method")
            {
                var head = arg.Split(new[] { "::" }, 2, StringSplitOptions.None);
                var p = head[1].Split(':');
                var tn = new[] { head[0], p[0] };
                var t = M.GetType(tn[0]);
                var attrs = MethodAttributes.Public | MethodAttributes.HideBySig | (p[2] == "static" ? MethodAttributes.Static : 0);
                var m = new MethodDefinition(tn[1], attrs, T(p[1]));
                if (p.Length > 3 && p[3].Length > 0)
                    foreach (var pn in p[3].Split(',')) m.Parameters.Add(new ParameterDefinition(T(pn)));
                Stub(m); t.Methods.Add(m);
            }
            else if (cmd[0] == "type")
            {
                var p = arg.Split(':');
                var ns = p[0].Substring(0, p[0].LastIndexOf('.')); var nm = p[0].Substring(p[0].LastIndexOf('.') + 1);
                if (p[1] == "enum")
                {
                    var t = new TypeDefinition(ns, nm, TypeAttributes.Public | TypeAttributes.Sealed, M.Import(typeof(Enum)));
                    t.Fields.Add(new FieldDefinition("value__", FieldAttributes.Public | FieldAttributes.SpecialName | FieldAttributes.RTSpecialName, M.TypeSystem.Int32));
                    int i = 0;
                    foreach (var v in p[2].Split(','))
                        t.Fields.Add(new FieldDefinition(v, FieldAttributes.Public | FieldAttributes.Static | FieldAttributes.Literal | FieldAttributes.HasDefault, t) { Constant = i++ });
                    M.Types.Add(t);
                }
                else
                {
                    var t = new TypeDefinition(ns, nm, TypeAttributes.Public | TypeAttributes.Class, M.TypeSystem.Object);
                    M.Types.Add(t);
                }
            }
        }
        if (a[1] != "-") { Sanitize(); asm.Write(a[1]); }
    }
}
