# How the port works

Colosseum Heroes shipped in 2011 as a Unity 3.4.2 game with only 32-bit ARM code. Unity 3.4 can't build
64-bit apps, and modern phones won't run 32-bit ones. The fix was to move the game, as it was, onto
Unity 2019.4, which builds 64-bit apps through IL2CPP.

## 1. Getting the project back

| Step | Problem | Solution |
|---|---|---|
| Read the data | AssetRipper can't read Unity 3.4 serialized files | `convert34to35.py` rewrites them to the Unity 3.5 layout using the exact 3.4.2 and 3.5.0 type trees |
| Scripts | The original scripts are compiled .NET DLLs | Decompiled to C#, including the UnityScript (JavaScript) assembly |
| Meshes | Old meshes use triangle strips and an old skinning format | `gen_meshes.py` rebuilds them as triangles with bone weights; `verify_meshes.py` checks them vertex by vertex |
| References | Exported prefabs and scenes point at the wrong objects | `RefTool.cs`, `check_refs.py` and `fix_yaml_components.py` repair them |
| Active state | Unity 3.x and 2019 treat active objects differently | `fix_active.py` and `inactive_parents.py` restore the original flags |

## 2. Making the code compile on Unity 2019.4

- **113 removed shortcuts** such as `.renderer`, `.collider` and `.animation` rewritten to `GetComponent<T>()`.
- **UnityScript/Boo runtime:** Unity 2019 no longer ships it, and IL2CPP can't run its dynamic code.
  `UnityScriptRuntime.cs` reimplements the parts the game uses in plain C#, including JavaScript-style arrays
  that grow when written past their end.
- **GUIText** was removed in Unity 2019.3. `GUITextCompat.cs` draws the same text with IMGUI, using the same
  positioning rules.
- **2011 SDKs** (Flurry, Facebook, Tapjoy, Twitter, old Google billing, Korean carrier stores) turned into no-ops.
  `CompatDialog.cs` replaces the Gamevil Java pop-ups.

## 3. Making it look right

| Symptom | Cause | Fix |
|---|---|---|
| Menu with no background, buttons missing, taps ignored | 180 of 205 materials had lost their texture links in export; the UI code then crashed on a missing `_MainTex` | `tools/materials/` reads every material in the original data, matches each texture by name and pixel size, and rewrites the `.mat` files |
| Background still invisible | Graphics tiers set to the **Vertex Lit** rendering path | Switched to **Forward** |
| Cameras drawing nothing | Exported cameras had an invalid projection-matrix mode | Set to the normal implicit mode |
| No sound | Audio clips referenced as native assets | Reference type corrected in 203 prefabs and scenes |
| Pink or black objects | Unity 3.4 built-in shaders don't exist in 2019 | Replacements in `unity/Assets/Shaders/Compat/` |
| Editor crash on load | Skin weights quality set to 0 | Restored to 4 bones |

## 4. Fitting modern phones

Wide 20:9 screens and high pixel density made the original controls and text either tiny or oversized. The
Options screen gained two settings, stored with PlayerPrefs:

- **BUTTONS:** 100%, 125%, 150%, 175% or 200%
- **TEXT:** 50%, 75%, 100% … 200%, for the stage, gold and kills counters. The default is 75%.

## 5. Building and testing without a person at the PC

- `setup_android.ps1` installs everything on drive D (the C drive was full). Downloads are SHA-1 checked,
  with mirrors and retries for a slow connection.
- `build_loop.ps1` watches a request file and runs Unity on each request. It closes the editor gently if
  compiling fails, and reloads itself when the script changes.
- `ColosseumHeroesPlayTest.cs` drives the game, saves screenshots, and dumps cameras, renderers, materials
  and errors to the log. A later run also rendered each camera alone over a test colour, which is how the
  invisible-background bug was narrowed down.
