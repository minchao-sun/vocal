"""Download, convert and plot the real-voice clips used in chapters 2, 3 and 4.

Sources (all openly licensed, labels assigned by the original researchers):
- Phonation Modes Dataset, Polina Proutskova (2012), CC BY-NC-SA, https://osf.io/pa3ha
  Sustained vowels on C4 by one female singer: 1811 breathy [a], 1841 pressed [a];
  neutral 1821 [a], 1900 [i], 1982 [u].
- Anderson, Klofstad, Mayew & Venkatachalam (2014), PLOS ONE 9(5): e97506, CC BY 4.0.
  Speaker 10 (male): S15 vocal fry, S16 normal voice.
- GTSinger (Zhang et al., NeurIPS 2024), CC BY-NC-SA 4.0, ZH-Tenor-1:
  Pharyngeal/尘埃/0006 (pharyngeal vs control, same melody);
  Mixed_Voice_and_Falsetto/老男孩/0002 (control, mixed voice, falsetto).

Usage (needs numpy, scipy, matplotlib, imageio-ffmpeg, requests; honours HTTPS_PROXY):
    python scripts/vocal-theory/make_real_clips.py [cache_dir]
"""
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.parse import quote

import imageio_ffmpeg
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import requests

SR = 22050
BOOK = Path(__file__).resolve().parents[2] / "vocal-theory"
AUDIO, IMAGES = BOOK / "audio", BOOK / "images"
CACHE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / ".cache" / "vocal-theory-clips"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
UA = {"User-Agent": "Mozilla/5.0 (personal study notes)"}

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

PHONATION = {"breathy": "1811", "neutral": "1821", "pressed": "1841"}
VOWELS = {"a": "1821", "i": "1900", "u": "1982"}
GTS = "https://huggingface.co/datasets/GTSinger/GTSinger/resolve/main/Chinese/ZH-Tenor-1/"
GTS_CLIPS = {
    "pharyngeal": ("Pharyngeal/尘埃", "0006", {"control": "Control_Group", "twang": "Pharyngeal_Group"}),
    "mix": ("Mixed_Voice_and_Falsetto/老男孩", "0002",
            {"natural": "Control_Group", "mixed": "Mixed_Voice_Group", "falsetto": "Falsetto_Group"}),
}
PLOS_BASE = "https://upload.wikimedia.org/wikipedia/commons/"
PLOS = {
    "fry": PLOS_BASE + "f/ff/Vocal-Fry-May-Undermine-the-Success-of-Young-Women-in-the-Labor-Market-pone.0097506.s015.oga",
    "normal": PLOS_BASE + "8/89/Vocal-Fry-May-Undermine-the-Success-of-Young-Women-in-the-Labor-Market-pone.0097506.s016.oga",
}


def osf_download(name):
    url = "https://api.osf.io/v2/nodes/pa3ha/files/osfstorage/"
    stack = [url]
    while stack:
        page = requests.get(stack.pop(), timeout=60).json()
        for it in page["data"]:
            a = it["attributes"]
            if a["kind"] == "folder":
                stack.append(it["relationships"]["files"]["links"]["related"]["href"])
            elif a["name"] == name:
                return requests.get(it["links"]["download"], timeout=600).content
        if page["links"].get("next"):
            stack.append(page["links"]["next"])
    raise FileNotFoundError(name)


def fetch_sources():
    CACHE.mkdir(parents=True, exist_ok=True)
    zpath = CACHE / "ND357A_16bit_cut_C4.zip"
    if not zpath.exists():
        zpath.write_bytes(osf_download(zpath.name))
    with zipfile.ZipFile(zpath) as z:
        for num in set(PHONATION.values()) | set(VOWELS.values()):
            member = next(n for n in z.namelist() if n.endswith(f"{num}.wav"))
            (CACHE / f"{num}.wav").write_bytes(z.read(member))
    for key, url in PLOS.items():
        path = CACHE / f"plos-{key}.oga"
        if not path.exists():
            path.write_bytes(requests.get(url, headers=UA, timeout=60).content)
    for key, (song, seg, groups) in GTS_CLIPS.items():
        for label, group in groups.items():
            path = CACHE / f"gts-{key}-{label}.wav"
            if not path.exists():
                r = requests.get(GTS + quote(f"{song}/{group}/{seg}.wav"), timeout=300)
                r.raise_for_status()
                path.write_bytes(r.content)


def decode(path):
    raw = subprocess.run([FFMPEG, "-loglevel", "error", "-i", str(path), "-f", "s16le", "-ac", "1",
                          "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(float) / 32768


def encode(x, name):
    AUDIO.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes()
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-",
                    "-codec:a", "libmp3lame", "-b:a", "96k", str(AUDIO / f"{name}.mp3")], input=pcm, check=True)
    print("audio", name)


def fade(x, ms=30):
    n = int(ms / 1000 * SR)
    x = x.copy()
    x[:n] *= np.linspace(0, 1, n)
    x[-n:] *= np.linspace(1, 0, n)
    return x


def phonation():
    clips = {mode: fade(decode(CACHE / f"{num}.wav")) for mode, num in PHONATION.items()}
    gain = 0.89 / max(np.abs(x).max() for x in clips.values())
    for mode, x in clips.items():
        encode(x * gain, f"ch2-phonation-{mode}")

    labels = {"breathy": "气息声（breathy）", "neutral": "中性（neutral）", "pressed": "挤压声（pressed）"}
    fig, axes = plt.subplots(3, 1, figsize=(8, 6.6), sharex=True)
    for ax, (mode, x) in zip(axes, clips.items()):
        mid = x[int(0.25 * len(x)): int(0.75 * len(x))]
        n = len(mid)
        spec = np.abs(np.fft.rfft(mid * np.hanning(n), 4 * n))
        f = np.fft.rfftfreq(4 * n, 1 / SR)
        db = 20 * np.log10(spec / spec.max() + 1e-9)
        sel = f <= 5000
        ax.plot(f[sel], db[sel], color="#c0392b", lw=0.8)
        ax.set_ylim(-70, 5)
        ax.set_ylabel("dB")
        ax.set_title(labels[mode], fontsize=11, loc="left")
        ax.grid(alpha=0.25)
    axes[-1].set_xlabel("频率（Hz）")
    fig.tight_layout()
    fig.savefig(IMAGES / "ch2-phonation-spectra.png", dpi=150)
    plt.close(fig)
    print("figure ch2-phonation-spectra")


def fry():
    clips = {k: fade(decode(CACHE / f"plos-{k}.oga")) for k in PLOS}
    gain = 0.89 / max(np.abs(x).max() for x in clips.values())
    for k, x in clips.items():
        encode(x * gain, f"ch3-speech-{k}")

    labels = {"fry": "气泡音（M0）", "normal": "正常说话（M1）"}
    fig, axes = plt.subplots(2, 1, figsize=(8, 4.6), sharex=True)
    for ax, (k, x) in zip(axes, clips.items()):
        rms = np.array([np.sqrt(np.mean(x[i:i + 2048] ** 2)) for i in range(0, len(x) - 2048, 256)])
        start = int(np.argmax(rms) * 256)
        seg = x[start: start + int(0.08 * SR)]
        ax.plot(np.arange(len(seg)) / SR * 1000, seg / np.abs(seg).max(), color="#2471a3", lw=0.9)
        ax.set_title(labels[k], fontsize=11, loc="left")
        ax.set_yticks([])
        ax.grid(alpha=0.25)
    axes[-1].set_xlabel("时间（毫秒）")
    fig.tight_layout()
    fig.savefig(IMAGES / "ch3-fry-waveform.png", dpi=150)
    plt.close(fig)
    print("figure ch3-fry-waveform")


def spectrum(x, fmax=5000):
    n = len(x)
    spec = np.abs(np.fft.rfft(x * np.hanning(n), 4 * n))
    f = np.fft.rfftfreq(4 * n, 1 / SR)
    sel = f <= fmax
    return f[sel], 20 * np.log10(spec[sel] / spec[sel].max() + 1e-9)


def vowels():
    clips = {v: fade(decode(CACHE / f"{num}.wav")) for v, num in VOWELS.items()}
    gap = np.zeros(int(0.35 * SR))
    gain = 0.89 / max(np.abs(x).max() for x in clips.values())
    joined = np.concatenate([part for x in clips.values() for part in (x, gap)][:-1])
    encode(joined * gain, "ch4-real-vowels")

    labels = {"a": "a（啊）", "i": "i（衣）", "u": "u（呜）"}
    fig, axes = plt.subplots(3, 1, figsize=(8, 6.6), sharex=True)
    for ax, (v, x) in zip(axes, clips.items()):
        f, db = spectrum(x[int(0.25 * len(x)): int(0.75 * len(x))], 4000)
        ax.plot(f, db, color="#c0392b", lw=0.8)
        ax.set_ylim(-70, 5)
        ax.set_ylabel("dB")
        ax.set_title(labels[v], fontsize=11, loc="left")
        ax.grid(alpha=0.25)
    axes[-1].set_xlabel("频率（Hz）")
    fig.tight_layout()
    fig.savefig(IMAGES / "ch4-real-vowels-spectra.png", dpi=150)
    plt.close(fig)
    print("figure ch4-real-vowels-spectra")


def voiced_ltas(x, fmax=5000, n=2048, hop=512):
    """Long-term average spectrum (dB) over the louder frames of a phrase."""
    frames = np.array([x[i:i + n] for i in range(0, len(x) - n, hop)])
    rms = np.sqrt((frames ** 2).mean(1))
    frames = frames[rms > 0.1 * rms.max()]
    P = (np.abs(np.fft.rfft(frames * np.hanning(n), axis=1)) ** 2).mean(0)
    f = np.fft.rfftfreq(n, 1 / SR)
    sel = f <= fmax
    return f[sel], 10 * np.log10(P[sel] / P[sel].max() + 1e-12)


def gts_pharyngeal():
    clips = {k: fade(decode(CACHE / f"gts-pharyngeal-{k}.wav")) for k in GTS_CLIPS["pharyngeal"][2]}
    gain = 0.89 / max(np.abs(x).max() for x in clips.values())
    for k, x in clips.items():
        encode(x * gain, f"ch4-gts-pharyngeal-{k}")

    styles = {"control": ("#7f8c8d", "自然唱法"), "twang": ("#c0392b", "咽音")}
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.axvspan(2000, 4000, color="#f5b041", alpha=0.2, label="2000–4000 Hz")
    for k, (c, label) in styles.items():
        f, db = voiced_ltas(clips[k])
        ax.plot(f, db, color=c, lw=1.4, label=label)
    ax.set_xlim(0, 5000)
    ax.set_ylim(-60, 3)
    ax.set_xlabel("频率（Hz）")
    ax.set_ylabel("相对强度（dB）")
    ax.legend(fontsize=9, loc="upper right")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(IMAGES / "ch4-gts-pharyngeal-spectrum.png", dpi=150)
    plt.close(fig)
    print("figure ch4-gts-pharyngeal-spectrum")


def gts_mix():
    clips = {k: fade(decode(CACHE / f"gts-mix-{k}.wav")) for k in GTS_CLIPS["mix"][2]}
    gain = 0.89 / max(np.abs(x).max() for x in clips.values())
    for k, x in clips.items():
        encode(x * gain, f"ch3-gts-{k}")


if __name__ == "__main__":
    IMAGES.mkdir(parents=True, exist_ok=True)
    fetch_sources()
    phonation()
    fry()
    vowels()
    gts_pharyngeal()
    gts_mix()
