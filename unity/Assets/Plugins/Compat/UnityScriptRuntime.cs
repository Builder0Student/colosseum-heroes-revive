// Rebuild marker (2026-11-09): edited so Unity recompiles every game assembly after Library\ScriptAssemblies lost them.
// Namespaces renamed to BooCompat / UnityScriptCompat: Unity 2019.4 still references its own
// Boo.Lang.dll and UnityScript.Lang.dll for Assembly-CSharp, and the original names clashed (CS0433).
// Replacement for the parts of Boo.Lang / UnityScript.Lang (Unity 3.x JavaScript runtime) that the
// decompiled UnityScript code uses. Pure C#, no Reflection.Emit, so it works under IL2CPP (ARM64).
using System;
using System.Collections;
using System.Reflection;

namespace BooCompat.Lang.Runtime
{
    public static class RuntimeServices
    {
        static bool IsNumeric(TypeCode c)
        {
            switch (c)
            {
                case TypeCode.Byte: case TypeCode.SByte: case TypeCode.Int16: case TypeCode.UInt16:
                case TypeCode.Int32: case TypeCode.UInt32: case TypeCode.Int64: case TypeCode.UInt64:
                case TypeCode.Single: case TypeCode.Double: case TypeCode.Decimal: case TypeCode.Char:
                    return true;
            }
            return false;
        }

        public static object Coerce(object value, Type toType)
        {
            if (value == null || toType == null || toType.IsInstanceOfType(value)) return value;
            Type from = value.GetType();
            if (toType.IsEnum && IsNumeric(Type.GetTypeCode(from)))
                return Enum.ToObject(toType, Convert.ToInt64(value));
            if (IsNumeric(Type.GetTypeCode(toType)) && value is IConvertible)
            {
                try { return Convert.ChangeType(value, toType); } catch (Exception) { }
            }
            MethodInfo op = FindConversion(from, from, toType) ?? FindConversion(toType, from, toType);
            if (op != null) return op.Invoke(null, new[] { value });
            return value;
        }

        static MethodInfo FindConversion(Type owner, Type from, Type to)
        {
            foreach (MethodInfo m in owner.GetMethods(BindingFlags.Public | BindingFlags.Static))
            {
                if ((m.Name == "op_Implicit" || m.Name == "op_Explicit") && m.ReturnType == to)
                {
                    ParameterInfo[] ps = m.GetParameters();
                    if (ps.Length == 1 && ps[0].ParameterType.IsAssignableFrom(from)) return m;
                }
            }
            return null;
        }

        public static bool EqualityOperator(object lhs, object rhs)
        {
            if (ReferenceEquals(lhs, rhs)) return true;
            if (lhs == null) return rhs.Equals(null);   // UnityEngine.Object.Equals(null) is true when destroyed
            if (rhs == null) return lhs.Equals(null);
            TypeCode lc = Type.GetTypeCode(lhs.GetType()), rc = Type.GetTypeCode(rhs.GetType());
            if (IsNumeric(lc) && IsNumeric(rc))
            {
                if (lc == TypeCode.Decimal || rc == TypeCode.Decimal) return Convert.ToDecimal(lhs) == Convert.ToDecimal(rhs);
                return Convert.ToDouble(lhs) == Convert.ToDouble(rhs);
            }
            System.Array la = lhs as System.Array, ra = rhs as System.Array;
            if (la != null && ra != null)
            {
                if (la.Length != ra.Length) return false;
                for (int i = 0; i < la.Length; i++)
                    if (!EqualityOperator(la.GetValue(i), ra.GetValue(i))) return false;
                return true;
            }
            return lhs.Equals(rhs);
        }

        public static bool ToBool(object value)
        {
            if (value == null) return false;
            if (value is bool) return (bool)value;
            UnityEngine.Object uo = value as UnityEngine.Object;
            if ((object)uo != null) return uo;   // implicit operator: false when destroyed
            TypeCode c = Type.GetTypeCode(value.GetType());
            if (IsNumeric(c)) return Convert.ToDouble(value) != 0.0;
            string s = value as string;
            if (s != null) return s.Length != 0;
            return true;
        }

        public static int UnboxInt32(object value)
        {
            if (value is int) return (int)value;
            return Convert.ToInt32(value);
        }

        public static float UnboxSingle(object value)
        {
            if (value is float) return (float)value;
            return Convert.ToSingle(value);
        }
    }
}

namespace UnityScriptCompat.Lang
{
    /// <summary>UnityScript's dynamic JavaScript-style Array.</summary>
    [Serializable]
    public class Array : ArrayList
    {
        public Array() { }

        public Array(int length)
        {
            for (int i = 0; i < length; i++) base.Add(null);
        }

        // UnityScript arrays behave like JavaScript arrays: writing past the end grows the array
        // (the game fills arrays such as StageData._warriorIndexArray by index), and reading past the
        // end gives null instead of throwing.
        public override object this[int index]
        {
            get { return index >= Count && index >= 0 ? null : base[index]; }
            set
            {
                while (Count <= index) base.Add(null);
                base[index] = value;
            }
        }

        public int length
        {
            get { return Count; }
            set
            {
                if (value < Count) RemoveRange(value, Count - value);
                while (Count < value) base.Add(null);
            }
        }

        public new void Add(object value) { base.Add(value); }

        public int Push(object value) { base.Add(value); return Count; }

        public object Pop()
        {
            if (Count == 0) return null;
            object v = this[Count - 1];
            RemoveAt(Count - 1);
            return v;
        }

        public object Shift()
        {
            if (Count == 0) return null;
            object v = this[0];
            RemoveAt(0);
            return v;
        }

        public void Unshift(object value) { Insert(0, value); }

        public void Clear() { base.Clear(); }

        public override string ToString() { return Join(","); }

        public string Join(string separator)
        {
            var sb = new System.Text.StringBuilder();
            for (int i = 0; i < Count; i++)
            {
                if (i > 0) sb.Append(separator);
                sb.Append(this[i]);
            }
            return sb.ToString();
        }
    }

    public static class Extensions
    {
        public static int get_length(System.Array a) { return a == null ? 0 : a.Length; }
    }

    public static class UnityRuntimeServices
    {
        sealed class ListUpdateableEnumerator : IEnumerator
        {
            readonly IList _list;
            int _index = -1;
            public ListUpdateableEnumerator(IList list) { _list = list; }
            public object Current { get { return _list[_index]; } }
            public bool MoveNext() { _index++; return _index < _list.Count; }
            public void Reset() { _index = -1; }
            public void Update(object value) { _list[_index] = value; }
        }

        public static IEnumerator GetEnumerator(object obj)
        {
            if (obj == null) return new object[0].GetEnumerator();
            IEnumerator e = obj as IEnumerator;
            if (e != null) return e;
            IList list = obj as IList;
            if (list != null && !list.IsReadOnly && !list.IsFixedSize) return new ListUpdateableEnumerator(list);
            if (list != null && !list.IsReadOnly) return new ListUpdateableEnumerator(list);
            return ((IEnumerable)obj).GetEnumerator();
        }

        public static void Update(IEnumerator e, object newValue)
        {
            ListUpdateableEnumerator le = e as ListUpdateableEnumerator;
            if (le != null) le.Update(newValue);
        }
    }
}
