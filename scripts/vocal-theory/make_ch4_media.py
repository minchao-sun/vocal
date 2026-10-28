"""Generate the synthesized audio demos and figures for chapter 4 (resonance).

Source-filter synthesis: a harmonic source (amplitude ~ 1/k, i.e. -6 dB/octave
after lip radiation) shaped by a cascade of formant resonators. Formant values
for adult male vowels follow Peterson & Barney (1952).

Usage (needs numpy, scipy, matplotlib, imageio-ffmpeg):
    python scripts/vocal-theory/make_ch4_media.py
"""
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter

SR = 22050
BOOK = Path(__file__).resolve().parents[2] / "vocal-theory"
AUDIO, IMAGES = BOOK / "audio", BOOK / "images"

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

BW = [90, 110, 160, 250, 300]
VOWELS = {
    "a": [730, 1090, 2440, 3400, 4200],
    "i": [270, 2290, 3010, 3500, 4200],
    "u": [300, 870, 2240, 3400, 4200],
}
VOWEL_BW = {"a": BW, "i": [60, 100, 170, 250, 300], "u": [60, 90, 160, 250, 300]}

NOTES = {"C4": 261.63, "D4": 293.66, "E4": 329.63, "F#4": 369.99, "G4": 392.00, "A4": 440.00, "A3": 220.00}


def resonator_gain(f, F, B):
    """Magnitude of a 2nd-order resonator, normalised to 1 at 0 Hz."""
    h = B / 2
    return (F**2 + h**2) / np.sqrt(((f - F) ** 2 + h**2) * ((f + F) ** 2 + h**2))


def tract_gain(f, formants, bands):
    g = np.ones_like(f, dtype=float)
    for F, B in zip(formants, bands):
        g *= resonator_gain(f, F, B)
    return g


def additive(f0, formants, bands, hop=64):
    """f0: per-sample Hz. formants/bands: callables t_index -> list, evaluated per frame."""
    n = len(f0)
    phase = 2 * np.pi * np.cumsum(f0) / SR
    frames = np.arange(0, n, hop)
    kmax = int(0.95 * (SR / 2) / f0.min())
    out = np.zeros(n)
    fr_f0 = f0[frames]
    F = np.array([formants(i) for i in frames])  # (frames, 5)
    B = np.array([bands(i) for i in frames])
    for k in range(1, kmax + 1):
        fk = k * fr_f0
        amp = np.where(fk < 0.95 * SR / 2, 1.0 / k, 0.0)
        for j in range(F.shape[1]):
            amp = amp * resonator_gain(fk, F[:, j], B[:, j])
        out += np.interp(np.arange(n), frames, amp) * np.sin(k * phase)
    return out


def envelope(n, attack=0.06, release=0.12):
    env = np.ones(n)
    a, r = int(attack * SR), int(release * SR)
    env[:a] = np.linspace(0, 1, a)
    env[-r:] = np.linspace(1, 0, r)
    return env


def noise_vowel(vowel, dur, rng):
    x = rng.standard_normal(int(dur * SR))
    for F, B in zip(VOWELS[vowel], VOWEL_BW[vowel]):
        r, th = np.exp(-np.pi * B / SR), 2 * np.pi * F / SR
        a = [1, -2 * r * np.cos(th), r * r]
        x = lfilter([sum(a)], a, x)
    return x * envelope(len(x), 0.08, 0.15)


def save(name, x, gain):
    AUDIO.mkdir(parents=True, exist_ok=True)
    y = np.clip(x * gain, -1, 1)
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "x.wav"
        wavfile.write(wav, SR, (y * 32767).astype(np.int16))
        subprocess.run(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(wav),
             "-ac", "1", "-codec:a", "libmp3lame", "-b:a", "96k", str(AUDIO / f"{name}.mp3")],
            check=True,
        )
    print("audio", name)


def norm_gain(*signals, peak=0.89):
    return peak / max(np.max(np.abs(s)) for s in signals)


# ---------------------------------------------------------------- demos

def vowels_same_pitch():
    hold, trans = 1.2, 0.2
    order = ["a", "i", "u"]
    total = len(order) * hold + (len(order) - 1) * trans
    n = int(total * SR)
    f0 = np.full(n, NOTES["A3"])

    def at(idx, table):
        t = idx / SR
        seg = int(t // (hold + trans))
        seg = min(seg, len(order) - 1)
        local = t - seg * (hold + trans)
        cur = np.array(table[order[seg]], float)
        if local > hold and seg + 1 < len(order):
            w = (local - hold) / trans
            return (1 - w) * cur + w * np.array(table[order[seg + 1]], float)
        return cur

    x = additive(f0, lambda i: at(i, VOWELS), lambda i: at(i, VOWEL_BW)) * envelope(n)
    save("ch4-01-vowels-same-pitch", x, norm_gain(x))


def whisper():
    rng = np.random.default_rng(7)
    gap = np.zeros(int(0.25 * SR))
    parts = []
    for v in ["a", "i", "u"]:
        parts += [noise_vowel(v, 1.0, rng), gap]
    x = np.concatenate(parts)
    save("ch4-02-whisper", x, norm_gain(x, peak=0.7))


def glide_f0():
    hold0, glide, hold1 = 0.5, 4.0, 0.8
    f_start, f_end = NOTES["C4"], NOTES["A4"]
    t = np.arange(int((hold0 + glide + hold1) * SR)) / SR
    s = np.clip((t - hold0) / glide, 0, 1)
    return t, f_start * (f_end / f_start) ** s


def f1_open(f0):
    return np.maximum(730.0, 1.1 * 2 * f0)


def cover_progress(f0):
    lo, hi = np.log(NOTES["D4"]), np.log(NOTES["F#4"])
    return np.clip((np.log(f0) - lo) / (hi - lo), 0, 1)


TWANG = [2500, 2800, 3150]
UPPER = np.array([2440.0, 3400.0, 4200.0])


def _formants(F1, F2, upper_mix):
    upper = UPPER + np.outer(upper_mix, np.array(TWANG) - UPPER)
    return np.column_stack([F1, F2, upper])


STRATEGIES = {
    "fixed": lambda f0: _formants(np.full_like(f0, 730.0), np.full_like(f0, 1090.0), np.zeros_like(f0)),
    "open": lambda f0: _formants(f1_open(f0), 1090.0 + 0.8 * (f1_open(f0) - 730.0), np.zeros_like(f0)),
    "closed": lambda f0: _formants(730.0 - 130.0 * cover_progress(f0), 1090.0 - 150.0 * cover_progress(f0),
                                   cover_progress(f0)),
}


def glides():
    t, f0 = glide_f0()
    signals = {}
    for name, fn in STRATEGIES.items():
        F = fn(f0)
        signals[name] = additive(f0, lambda i, F=F: F[i], lambda i: BW) * envelope(len(f0))
    g = norm_gain(*signals.values())
    for idx, (name, x) in enumerate(signals.items(), start=3):
        save(f"ch4-0{idx}-glide-{name}", x, g)
    return t, f0, signals


def twang():
    n = int(2.0 * SR)
    f0 = np.full(n, NOTES["D4"])
    normal = additive(f0, lambda i: VOWELS["a"], lambda i: BW) * envelope(n)
    clustered = additive(f0, lambda i: [730, 1090] + TWANG, lambda i: [90, 110, 120, 150, 200]) * envelope(n)
    x = np.concatenate([normal, np.zeros(int(0.4 * SR)), clustered])
    save("ch4-06-twang", x, norm_gain(x))


# ---------------------------------------------------------------- figures

def fig_harmonics_vowels():
    f0 = NOTES["A3"]
    k = np.arange(1, int(4000 / f0) + 1)
    f = np.linspace(1, 4000, 2000)
    fig, axes = plt.subplots(2, 1, figsize=(8, 5.6), sharex=True)
    for ax, v, label in zip(axes, ["a", "i"], ["啊", "衣"]):
        Fs, Bs = VOWELS[v], VOWEL_BW[v]
        ref = (1 / k * tract_gain(k * f0, Fs, Bs)).max()
        amps = 20 * np.log10(1 / k * tract_gain(k * f0, Fs, Bs) / ref)
        fe = f[f >= f0]
        env = 20 * np.log10(tract_gain(fe, Fs, Bs) * f0 / fe / ref)
        ax.plot(fe, env, "--", color="#999", lw=1, label="声道的放大曲线（共振峰）")
        ax.vlines(k * f0, -60, amps, color="#c0392b", lw=2.2, label=f"泛音（基频 {f0:.0f} Hz 的整数倍）")
        for j, (name, ha, dx) in enumerate([("F1", "right", -25), ("F2", "left", 25)]):
            ax.annotate(f"{name} ≈ {Fs[j]}", (Fs[j] + dx, 4), ha=ha, fontsize=9, color="#555")
        ax.set_ylim(-60, 10)
        ax.set_ylabel("相对强度（dB）")
        ax.set_title(f"在 A3 上唱“{label}”", fontsize=11, loc="left")
        ax.grid(alpha=0.25)
    axes[0].legend(fontsize=8.5, loc="upper right")
    axes[1].set_xlabel("频率（Hz）")
    fig.tight_layout()
    fig.savefig(IMAGES / "ch4-harmonics-vowels.png", dpi=150)
    plt.close(fig)
    print("figure ch4-harmonics-vowels")


def pitch_axis(ax):
    ticks = ["C4", "D4", "E4", "F#4", "G4", "A4"]
    ax.set_xscale("log")
    ax.set_xticks([NOTES[n] for n in ticks])
    ax.set_xticklabels(ticks)
    ax.minorticks_off()
    ax.set_xlim(NOTES["C4"] * 0.98, NOTES["A4"] * 1.02)
    ax.set_xlabel("唱的音高")


def fig_crossing():
    f0 = np.geomspace(NOTES["C4"], NOTES["A4"], 300)
    fig, ax = plt.subplots(figsize=(8, 4.4))
    ax.axhspan(650, 800, color="#f5b041", alpha=0.25, label="“啊”的第一共振峰 F1（约 650–800 Hz）")
    ax.axhline(730, color="#d68910", lw=1)
    for k, c in [(1, "#7f8c8d"), (2, "#c0392b"), (3, "#2471a3")]:
        ax.plot(f0, k * f0, color=c, lw=2.4 if k == 2 else 1.6, label=f"第 {k} 泛音（{k} × 基频）")
    ax.annotate("第二泛音在 F#4 附近\n越过“啊”的 F1", (NOTES["F#4"], 740), (392, 470),
                arrowprops=dict(arrowstyle="->", color="#333"), fontsize=10)
    pitch_axis(ax)
    ax.set_ylim(200, 1400)
    ax.set_ylabel("频率（Hz）")
    ax.legend(fontsize=8.5, loc="upper left")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(IMAGES / "ch4-crossing.png", dpi=150)
    plt.close(fig)
    print("figure ch4-crossing")


def fig_strategies():
    f0 = np.geomspace(NOTES["C4"], NOTES["A4"], 300)
    fig, ax = plt.subplots(figsize=(8, 4.4))
    ax.plot(f0, 2 * f0, color="#c0392b", lw=2.6, label="第二泛音（2 × 基频）")
    styles = {"fixed": ("#7f8c8d", "--", "不调整：F1 固定在 730 Hz"),
              "open": ("#e67e22", "-", "开放策略：F1 追着第二泛音往上走"),
              "closed": ("#2471a3", "-", "关闭策略：F1 在 D4 到 F#4 之间略微降低")}
    for name, (c, ls, label) in styles.items():
        F1 = STRATEGIES[name](f0)[:, 0]
        ax.plot(f0, F1, color=c, ls=ls, lw=2, label=label)
    pitch_axis(ax)
    ax.set_ylim(400, 1100)
    ax.set_ylabel("频率（Hz）")
    ax.legend(fontsize=8.5, loc="upper left")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(IMAGES / "ch4-strategies.png", dpi=150)
    plt.close(fig)
    print("figure ch4-strategies")


def strategy_levels(f0, name):
    """Overall level and 2-4 kHz level (dB) of the synthesized spectrum at each pitch."""
    F = STRATEGIES[name](f0)
    total, band = [], []
    for i, f in enumerate(f0):
        k = np.arange(1, int(0.95 * (SR / 2) / f) + 1)
        p = (1 / k * tract_gain(k * f, F[i], BW)) ** 2
        total.append(10 * np.log10(p.sum()))
        fk = k * f
        w = np.clip((fk - 1800) / 400, 0, 1) * np.clip((4200 - fk) / 400, 0, 1)
        band.append(10 * np.log10((p * w).sum()))
    return np.array(total), np.array(band)


def fig_strategy_levels():
    f0 = np.geomspace(NOTES["C4"], NOTES["A4"], 300)
    styles = {"fixed": ("#7f8c8d", "--", "不调整"), "open": ("#e67e22", "-", "开放策略"),
              "closed": ("#2471a3", "-", "关闭策略")}
    levels = {n: strategy_levels(f0, n) for n in styles}
    ref_total = levels["fixed"][0][0]
    ref_band = levels["fixed"][1][0]
    fig, axes = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
    for name, (c, ls, label) in styles.items():
        total, band = levels[name]
        axes[0].plot(f0, total - ref_total, color=c, ls=ls, lw=2, label=label)
        axes[1].plot(f0, band - ref_band, color=c, ls=ls, lw=2, label=label)
    axes[0].set_title("整体音量（相对于 C4）", fontsize=11, loc="left")
    axes[1].set_title("2000–4000 Hz 频段的能量（相对于 C4）：决定声音是否明亮、有穿透力", fontsize=11, loc="left")
    for ax in axes:
        ax.set_ylabel("dB")
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8.5, loc="upper left")
    pitch_axis(axes[1])
    fig.tight_layout()
    fig.savefig(IMAGES / "ch4-strategy-levels.png", dpi=150)
    plt.close(fig)
    print("figure ch4-strategy-levels")


def fig_twang():
    f0 = NOTES["D4"]
    k = np.arange(1, int(5000 / f0) + 1)
    normal = 1 / k * tract_gain(k * f0, VOWELS["a"], BW)
    tw = 1 / k * tract_gain(k * f0, [730, 1090] + TWANG, [90, 110, 120, 150, 200])
    ref = max(normal.max(), tw.max())
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.axvspan(2000, 4000, color="#f5b041", alpha=0.2, label="2000–4000 Hz：人耳最敏感的频段")
    ax.vlines(k * f0 - 18, -70, 20 * np.log10(normal / ref), color="#7f8c8d", lw=2.4, label="普通的“啊”")
    ax.vlines(k * f0 + 18, -70, 20 * np.log10(tw / ref), color="#c0392b", lw=2.4, label="第三到第五共振峰聚拢（模拟咽音）")
    ax.set_xlim(0, 5000)
    ax.set_ylim(-70, 5)
    ax.set_xlabel("频率（Hz）")
    ax.set_ylabel("相对强度（dB）")
    ax.legend(fontsize=8.5, loc="upper right")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(IMAGES / "ch4-twang-spectrum.png", dpi=150)
    plt.close(fig)
    print("figure ch4-twang-spectrum")


if __name__ == "__main__":
    IMAGES.mkdir(parents=True, exist_ok=True)
    vowels_same_pitch()
    whisper()
    glides()
    twang()
    fig_harmonics_vowels()
    fig_crossing()
    fig_strategies()
    fig_strategy_levels()
    fig_twang()
