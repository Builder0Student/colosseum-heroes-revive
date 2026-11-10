"""Replace AssetRipper's empty .audioclip placeholders with the original WAV/MP3 data, keeping each asset GUID.

Usage: fix_audio.py <converted Data dir> <InfoJson 3.5.0.json> <exported Assets dir>
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(__file__))
import sf8, tt

data_dir, tree_path, assets = sys.argv[1:4]
T = tt.load_trees(tree_path)
clips = {}
for f in [x for x in sf8.data_files(data_dir) if x != "unity default resources"]:
    for o in sf8.SF8(os.path.join(data_dir, f)).objects:
        if o.class_id == 83:
            d, _ = tt.read(T[83], o.data)
            clips[d["m_Name"]] = d

META = """fileFormatVersion: 2
guid: {guid}
AudioImporter:
  externalObjects: {{}}
  serializedVersion: 6
  defaultSettings:
    loadType: {load}
    sampleRateSetting: 0
    sampleRateOverride: 44100
    compressionFormat: 1
    quality: {quality}
    conversionMode: 0
  platformSettingOverrides: {{}}
  forceToMono: 0
  normalize: 1
  preloadAudioData: 1
  loadInBackground: {bg}
  ambisonic: 0
  3D: {is3d}
  userData:
  assetBundleName:
  assetBundleVariant:
"""

adir = os.path.join(assets, "AudioClip")
done = 0
for fn in sorted(os.listdir(adir)):
    if not fn.endswith(".audioclip"):
        continue
    name = fn[:-len(".audioclip")]
    d = clips[name]
    data = d["m_AudioData"]
    ext = {20: ".wav", 13: ".mp3"}[d["m_Type"]]
    if ext == ".wav":
        assert data[:4] == b"RIFF"
    guid = re.search(r"^guid: (\w+)", open(os.path.join(adir, fn + ".meta")).read(), re.M).group(1)
    music = len(data) > 500_000
    os.remove(os.path.join(adir, fn)); os.remove(os.path.join(adir, fn + ".meta"))
    open(os.path.join(adir, name + ext), "wb").write(data)
    open(os.path.join(adir, name + ext + ".meta"), "w").write(
        META.format(guid=guid, load=1 if music else 0, quality=0.7 if music else 1,
                    bg=1 if music else 0, is3d=1 if d["m_3D"] else 0))
    done += 1
print(f"replaced {done} clips")
