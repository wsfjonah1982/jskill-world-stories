"""Short footage from an approved keyframe: one Seedance first-frame clip (the world's short_min–short_max seconds).

Each liked keyframe with mode "short" in approval.json gets a shot script `script/<K>.json`, written by the Agent:
  {"title": "...", "duration": 15, "recap": "what the first frame shows",
   "shots": [[0, 5, "[MS, static] action with <Tag>s", "{Name: \"line\"} {Name2: \"line\"}"], ...]}

Steps:
  prompts  write `script/<K>.md` (the readable script) and `prompt/<K>_video.txt` from the canon blocks (style, video
           definitions, voices, location, video rules, audio rule) and check the shot timings. A prompt the user edited
           by hand (marked by prompt/<K>_video.edited) is kept.
  videos   render output/<K>.mp4 (only after the user marked the script Generate: videos are paid), then check it
  check    review a rendered clip (free): output/<K>_frames.jpg (a 3x2 contact sheet across the clip) and
           output/<K>_check.md (the audio transcribed with faster-whisper, each scripted line matched against it with
           its timing). Music cannot be detected this way: still listen once.

Usage:  python short_footage.py <idea.json> prompts|videos|check [K2 K3 ...]
"""
import difflib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _world import wl  # noqa: E402
from keyframes import Idea, dialogue_only, short_prompt  # noqa: E402


class Shorts(Idea):
    def __init__(self, idea_path):
        super().__init__(idea_path)
        self.kfs = {k["id"]: k for k in self.spec["keyframes"]}
        self.sdir = self.out / "script"
        self.sdir.mkdir(parents=True, exist_ok=True)

    def chosen(self, ids):
        if ids:
            return ids
        ap = self.out / "approval.json"
        if not ap.is_file():
            sys.exit("no approval.json in the task folder: give the keyframe ids")
        ks = json.loads(ap.read_text(encoding="utf-8"))["keyframes"]
        return [k for k, d in ks.items() if d.get("like") and d.get("mode") == "short"]

    def script(self, kid):
        f = self.sdir / f"{kid}.json"
        if not f.is_file():
            sys.exit(f"{kid}: script/{kid}.json is missing (the Agent writes it first)")
        return json.loads(f.read_text(encoding="utf-8"))

    def check(self, kid, sc):
        errs, t = [], 0
        for a, b, act, au in sc["shots"]:
            if a != t:
                errs.append(f"shot starting at {a}s does not follow the previous one ending at {t}s")
            t = b
        if t != sc["duration"]:
            errs.append(f"shots end at {t}s, duration is {sc['duration']}s")
        lo, hi = self.w.fmt["short_min"], self.w.fmt["short_max"]
        if not lo <= sc["duration"] <= hi:
            errs.append(f"duration {sc['duration']}s is outside {lo}–{hi}s")
        if "--" in json.dumps(sc, ensure_ascii=False):
            errs.append("'--' in the script silently truncates the prompt")
        return [f"{kid}: {e}" for e in errs]

    def prompts(self, ids):
        errs = []
        for kid in self.chosen(ids):
            sc, k = self.script(kid), self.kfs[kid]
            errs += self.check(kid, sc)
            if (self.pdir / f"{kid}_video.edited").exists():
                print(kid, "prompt kept (edited by hand)")
            else:
                (self.pdir / f"{kid}_video.txt").write_text(short_prompt(self.w, k, sc), encoding="utf-8")
            rows = "".join(f"| {a}–{b}s | Shot {i} | {act} | {dialogue_only(au)} |\n"
                           for i, (a, b, act, au) in enumerate(sc["shots"], 1))
            md = (f"# {kid} · {sc['title']}\n\n- Short footage, {sc['duration']}s, {self.w.fmt['ratio']}, "
                  f"{self.w.fmt['resolution']}\n- Location: `{k['location']}` · first frame: `output/{kid}.jpg`\n"
                  f"- Opens on: {sc['recap']}\n\n| Time | Shot | Visual | Dialogue |\n|---|---|---|---|\n{rows}")
            (self.sdir / f"{kid}.md").write_text(md, encoding="utf-8")
            print(kid, "prompt and script written", f"({len(sc['shots'])} shots, {sc['duration']}s)")
        for e in errs:
            print("ERROR", e)
        return not errs

    def videos(self, ids):
        if not self.prompts(ids):
            sys.exit(1)
        for kid in self.chosen(ids):
            kf = self.odir / f"{kid}.jpg"
            if not kf.exists():
                print(kid, f"no keyframe output/{kid}.jpg", flush=True)
                continue
            for attempt in (1, 2):
                ok, msg = wl.gen_video(self.w, kf, self.pdir / f"{kid}_video.txt", self.script(kid)["duration"],
                                       self.odir / f"{kid}.mp4", self.ldir)
                print(kid, f"attempt {attempt}", msg, flush=True)
                if ok or "paid" in msg:  # submitted = paid: recover with resume_video_task.py, never re-submit
                    break
            if (self.odir / f"{kid}.mp4").exists():
                self.review(kid)

    def review(self, kid):
        """Contact sheet + transcript check of output/<K>.mp4; prints a one-line verdict per scripted line."""
        mp4 = self.odir / f"{kid}.mp4"
        if not mp4.exists():
            return print(kid, f"no output/{kid}.mp4")
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                    str(mp4)], capture_output=True, text=True).stdout.strip() or 0)
        sheet = self.odir / f"{kid}_frames.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-vf",
                        f"fps=6/{max(dur, 1):.3f},scale=640:-1,tile=3x2", "-frames:v", "1", str(sheet)], check=True)
        sc = self.script(kid)
        want = [(a, b, spk.strip(), line) for a, b, _, au in sc["shots"]
                for spk, line in re.findall(r'\{\s*([^:(]+?)\s*(?:\([^)]*\))?\s*:\s*"([^"]*)"\s*\}', au or "")]
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            heard, note = [], "faster-whisper is not installed (pip install faster-whisper): no transcript"
        else:
            model = WhisperModel("small", device="cpu", compute_type="int8")
            segs, _ = model.transcribe(str(mp4), language="en", word_timestamps=False, vad_filter=True)
            heard, note = [(g.start, g.end, g.text.strip()) for g in segs], ""

        def norm(t):
            t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
            return " ".join(re.sub(r"[^a-z0-9 ]", " ", t.lower()).split())

        rows, issues = [], []
        for a, b, spk, line in want:
            best = (0.0, None)
            for i in range(len(heard)):  # a line may span up to three transcript segments
                for j in range(i, min(i + 3, len(heard))):
                    txt = " ".join(h[2] for h in heard[i:j + 1])
                    r = difflib.SequenceMatcher(None, norm(line), norm(txt)).ratio()
                    if r > best[0]:
                        best = (r, (heard[i][0], heard[j][1], txt))
            r, m = best
            when = f"{m[0]:.1f}–{m[1]:.1f}s" if m else "–"
            ok = r >= 0.6 and m and m[0] >= a - 1 and m[1] <= b + 1.5
            verdict = "ok" if ok else ("missing" if r < 0.6 else "off-time")
            if not ok:
                issues.append(f"{spk} {verdict}: \"{line}\"")
            rows.append(f"| {a}–{b}s | {spk} | {line} | {m[2] if m else ''} | {when} | {r:.0%} {verdict} |")
        md = (f"# {kid} · video check\n\n- Clip: `output/{kid}.mp4`, {dur:.1f}s · frames: `output/{kid}_frames.jpg`\n"
              + (f"- {note}\n" if note else "")
              + "- Music and sound effects are not detected here: listen once.\n\n"
              "| Shot | Speaker | Scripted | Heard | When | Match |\n|---|---|---|---|---|---|\n" + "\n".join(rows)
              + "\n\n## Full transcript\n\n" + "\n".join(f"- {s0:.1f}–{s1:.1f}s {t}" for s0, s1, t in heard) + "\n")
        (self.odir / f"{kid}_check.md").write_text(md, encoding="utf-8")
        print(kid, "check:", note or ("all lines heard on time" if not issues else "; ".join(issues)),
              f"-> output/{kid}_check.md, output/{kid}_frames.jpg", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")  # Windows consoles (cp1252) cannot print every line of dialogue
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    sh = Shorts(sys.argv[1])
    step, ids = sys.argv[2], sys.argv[3:]
    if step == "prompts":
        sys.exit(0 if sh.prompts(ids) else 1)
    elif step == "check":
        for kid in sh.chosen(ids):
            sh.review(kid)
    elif step == "videos":
        wl.require(("python", "video", "world"), sh.w)
        sh.videos(ids)
    else:
        sys.exit(f"unknown step '{step}': prompts | videos | check")
