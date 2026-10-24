"""Long take (1–2 min) from one keyframe: storyboard first, then video segments stitched into one film.

One story spec (JSON) drives everything:
  1. grid       one Seedream image: a COLSxROWS storyboard of panels (3x3 = 9 panels by default)
  2. crops      cut the grid into panels (gutters auto-detected)
  3. keyframes  each segment's first panel redrawn at the world's keyframe size (panel crop + sheets + location)
  4. page       storyboard.html: grid, keyframes, segment plan, review buttons, the film when present
  5. videos     one Seedance first-frame clip per segment (paid: only after the user approved the storyboard)
  6. stitch     ffmpeg join with the V-6 trim (last 6 frames of each clip, first frame of the next)

Usage:  python storyboard_film.py <story.json> <step> [segment ids...]
        steps: grid | crops | keyframes | page | videos | stitch | preview (= grid crops keyframes page)

Spec fields: name, title, out_dir (relative to the world folder), grid {cols, rows, size}, segment_seconds (default:
the world's), location (a Setting.md location key), cast (optional, default the world's main cast), setting_ref
(optional image, default the location picture), prop_rule (optional, episode-only props), canon_props (optional,
true = paste the full props block), panels[cols*rows]{seg, beat, fix?}, segments{S1..}{recap, shots[[a, b, action,
audio], ...]}, review_notes (optional).

Style, characters, the location and the recurring props are NOT in the spec: they are read from the world's canon
(Identities.md, Setting.md) on every run, so every film stays consistent.
"""
import base64
import html
import io
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _world import pagenav, wl  # noqa: E402
from keyframes import setting  # noqa: E402

# Dependencies each step needs (Dependencies.md); checked before any third-party import so a missing one
# returns the DEPENDENCY ERROR message instead of a traceback.
STEP_DEPS = {"grid": ("python", "image", "world"), "crops": ("python",), "keyframes": ("python", "image", "world"),
             "page": ("python",), "videos": ("python", "video", "world"), "stitch": ("python", "ffmpeg"),
             "preview": ("python", "image", "world")}

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

# Review on the storyboard page: approve (→ the Agent renders the videos) or ask for changes, with a note per
# segment; "Copy feedback" puts it on the clipboard for the user to paste to the Agent. Kept in the browser.
DECIDE_HTML = """<section class="fb"><h2>Your review</h2>
<div class="fbseg"><button type="button" data-dec="approve">✓ Approve: generate the videos<small>paid renders, made by the Agent</small></button>
<button type="button" data-dec="revise">✎ Needs changes<small>use the notes below and under each segment</small></button></div>
<textarea id="fbNote" placeholder="General notes (optional)"></textarea>
<p class="fbhint">Your choice and notes are kept in this browser. When done, click <b>Copy feedback</b> and paste it to the Agent.</p></section>"""
FEEDBACK_JS = """<div class="fbbar"><span id="fbSum"></span><span id="fbToast"></span><button type="button" id="fbCopy">Copy feedback</button></div>
<style>
.fb .fbseg{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.fb .fbseg button{flex:1;min-width:200px;border:1px solid var(--line);background:transparent;color:var(--ink);border-radius:8px;padding:8px 10px;font:inherit;cursor:pointer;text-align:left}
.fb .fbseg button small{display:block;color:var(--muted);font-size:12px}
.fb .fbseg button[aria-pressed=true]{border-color:var(--accent);color:var(--accent);font-weight:600}
.fbhint{color:var(--muted);font-size:13px;margin:6px 0 0}
main{padding-bottom:90px}
.fbbar{position:fixed;left:0;right:0;bottom:0;background:var(--card);border-top:1px solid var(--line);padding:10px 16px;display:flex;gap:12px;align-items:center;justify-content:flex-end;flex-wrap:wrap;font-size:14px}
.fbbar #fbSum{margin-right:auto;color:var(--muted)} .fbbar #fbToast{color:var(--accent)}
.fbbar button{border:0;background:var(--accent);color:var(--card);border-radius:8px;padding:8px 14px;font:inherit;cursor:pointer}
</style>
<script>
(() => {
const ST = /*STORY*/{};
const KEY = 'storyboard-feedback:' + ST.out_dir;
let F = {};
try { F = JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { F = {}; }
F.notes = F.notes || {};
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(F)); } catch (e) {} sum(); };
const btns = document.querySelectorAll('[data-dec]');
const show = () => btns.forEach(b => b.setAttribute('aria-pressed', b.dataset.dec === F.decision));
btns.forEach(b => b.onclick = () => { F.decision = F.decision === b.dataset.dec ? undefined : b.dataset.dec; show(); save(); });
const note = document.getElementById('fbNote');
note.value = F.note || ''; note.oninput = () => { F.note = note.value; save(); };
document.querySelectorAll('textarea[data-seg]').forEach(t => {
  t.value = F.notes[t.dataset.seg] || '';
  t.oninput = () => { F.notes[t.dataset.seg] = t.value; save(); };
});
function feedback() {
  const notes = {};
  for (const [k, v] of Object.entries(F.notes)) if (v && v.trim()) notes[k] = v.trim();
  return {page: 'storyboard', story: ST.name, title: ST.title, out_dir: ST.out_dir, exported: new Date().toISOString(),
          decision: F.decision || 'undecided', note: (F.note || '').trim(), segment_notes: notes};
}
function sum() {
  const n = Object.values(F.notes).filter(v => v && v.trim()).length;
  document.getElementById('fbSum').textContent =
    (F.decision === 'approve' ? 'Approved: generate the videos' : F.decision === 'revise' ? 'Needs changes' : 'No decision yet') +
    ` · ${n} segment note${n === 1 ? '' : 's'}`;
}
const toast = t => { const el = document.getElementById('fbToast'); el.textContent = t; setTimeout(() => el.textContent = '', 3000); };
document.getElementById('fbCopy').onclick = async () => {
  const txt = JSON.stringify(feedback(), null, 2);
  try { await navigator.clipboard.writeText(txt); toast('Copied: paste it to the Agent'); }
  catch (e) {
    const t = document.createElement('textarea'); t.value = txt; document.body.appendChild(t); t.select();
    try { document.execCommand('copy'); toast('Copied: paste it to the Agent'); } catch (e2) { toast('Copy failed'); }
    t.remove();
  }
};
show(); sum();
})();
</script>"""


def dialogue_only(audio):
    """Keep only the {Speaker: "line"} parts of a shot's audio cue; music (...) and sound <...> cues are dropped
    (the world's audio rule decides what else is heard)."""
    return " ".join(re.findall(r"\{[^}]*\}", audio or ""))


class Story:
    def __init__(self, spec_path):
        spec_path = Path(spec_path).resolve()
        self.w = w = wl.World(wl.find_world(spec_path.parent))
        self.spec = json.loads(spec_path.read_text(encoding="utf-8"))
        self.spec.setdefault("location", self.spec.get("scene"))  # "scene" is the name; "location" still works
        s = self.spec
        s.setdefault("segment_seconds", w.fmt["segment_seconds"])
        self.out = w.p(s["out_dir"])
        self.pdir, self.odir, self.ldir = self.out / "prompt", self.out / "output", self.out / "log"
        for d in (self.pdir, self.odir, self.ldir):
            d.mkdir(parents=True, exist_ok=True)
        self.cols, self.rows = s["grid"]["cols"], s["grid"]["rows"]
        self.grid_img = self.odir / "storyboard_grid.jpg"
        self.segs = list(s["segments"])
        self.cast = s.get("cast") or w.default_cast()
        self.sheets = [str(w.sheet(c)) for c in self.cast]
        ref = w.p(s["setting_ref"]) if s.get("setting_ref") else w.location_image(s.get("location") or "_")
        self.setting = [str(ref)] if ref.is_file() else []
        self.neg_img = "no panel numbers, " + w.neg_image
        self.one_each = w.one_each(self.cast)
        # Canonical background info, re-read from Identities.md / Setting.md on every run.
        for k in ("style", "characters"):
            if k in s:
                print(f"note: spec field '{k}' is ignored; it comes from Identities.md")
        if s.get("location") not in w.locations():
            raise SystemExit(f"spec needs 'location', one of: {', '.join(w.locations())} (Setting.md)")
        self.style = w.get("style")
        self.chars = w.get("characters")
        # The canon props list names every recurring prop; pasted into every prompt, the model draws them all.
        # It is used only when the spec sets "canon_props": true; otherwise prop_rule names the episode's props.
        props = w.get("props") if s.get("canon_props") else w.no_props_rule
        self.env = " ".join(filter(None, (setting(w, s["location"], self.cast), props, s.get("prop_rule"))))
        self.defs = w.get("video-defs") + " " + w.get("voice", "")
        self.vid_rules = w.get("video-rules") + "\n" + w.get("audio")

    # ---------- helpers ----------
    def run_image(self, refs, prompt_file, out, size):
        with wl.patched_config(wl.image_settings(self.w, size)):
            return self._image(refs, prompt_file, out)

    def _image(self, refs, prompt_file, out):
        return wl.gen_image(refs, prompt_file, out, self.ldir)

    def first_panel(self, seg):
        return next(i for i, p in enumerate(self.spec["panels"]) if p["seg"] == seg)

    def keyframe(self, seg):
        return self.odir / f"{seg}_keyframe.jpg"

    # ---------- 1. grid ----------
    def grid(self):
        s = self.spec
        n = self.cols * self.rows
        assert len(s["panels"]) == n, f"need {n} panels, spec has {len(s['panels'])}"
        pos = lambda i: f"row {i // self.cols + 1}, column {i % self.cols + 1}"
        lines = "\n".join(f"Panel {i+1} ({pos(i)}): {p['beat']}" for i, p in enumerate(s["panels"]))
        ref_note = ("; ".join(f"image {i} is the character sheet of {self.w.char_label(c)}" for i, c in enumerate(self.cast, 1))
                    + (f"; image {len(self.cast) + 1} shows the setting to keep consistent" if self.setting else "")
                    + ". Use them for identity only.")
        ref_note = ref_note[0].upper() + ref_note[1:]
        prompt = (f"{self.style}. A single storyboard sheet: a grid of {self.cols} columns by {self.rows} rows = {n} equal "
                  f"{self.w.fmt['ratio']} panels separated by thin white gutters, read left to right, top to bottom. Each panel "
                  f"is a finished colour frame of the same short film.\n{ref_note}\n"
                  f"Characters, identical in every panel: {self.chars}\nSetting, identical in every panel: {self.env}\n{lines}\n"
                  f"In every panel {self.one_each}. {self.neg_img}\n")
        pf = self.pdir / "grid.txt"
        pf.write_text(prompt, encoding="utf-8")
        if self.grid_img.exists():
            print("grid exists")
            return
        print("grid", self.run_image(self.sheets + self.setting, pf, self.grid_img, s["grid"]["size"]))

    # ---------- 2. crops ----------
    def crops(self):
        g = Image.open(self.grid_img).convert("RGB")
        a = np.asarray(g.convert("L")).astype(float)

        def bands(profile, n):
            light = profile > 235
            runs, start = [], None
            for i, v in enumerate(list(light) + [False]):
                if not v and start is None:
                    start = i
                if v and start is not None:
                    runs.append((start, i)); start = None
            if start is not None and start < len(profile):
                runs.append((start, len(profile)))
            runs = sorted(sorted(runs, key=lambda r: r[1] - r[0], reverse=True)[:n])
            if len(runs) != n:  # gutters not found — fall back to equal split
                step = len(profile) / n
                runs = [(int(i * step), int((i + 1) * step)) for i in range(n)]
            return runs

        cols, rows = bands(a.mean(0), self.cols), bands(a.mean(1), self.rows)
        for i in range(self.cols * self.rows):
            (x0, x1), (y0, y1) = cols[i % self.cols], rows[i // self.cols]
            g.crop((x0, y0, x1, y1)).save(self.odir / f"panel_{i+1:02d}.jpg", quality=95)
        print("crops", self.cols * self.rows, "cols", cols, "rows", rows)

    # ---------- 3. keyframes ----------
    def keyframes(self, ids):
        s = self.spec

        def one(seg):
            out = self.keyframe(seg)
            if out.exists():
                return seg, "exists"
            i = self.first_panel(seg)
            fix = s["panels"][i].get("fix", "")
            pf = self.pdir / f"{seg}_keyframe.txt"
            pf.write_text(
                f"{self.style}. {self.w.ratio_words} composition, full-bleed, no borders.\n"
                "Image 1 is a small storyboard panel: recreate exactly its composition, camera framing, character poses, "
                "setting and lighting as one finished full-resolution frame with crisp detail. "
                + "; ".join(f"image {i} is the character sheet of {self.w.char_label(c)}" for i, c in enumerate(self.cast, 2))
                + (f"; image {len(self.cast) + 2} shows the setting" if self.setting else "") + ". Use them for identity.\n"
                f"Scene: {s['panels'][i]['beat']} {fix}\nCharacters: {self.chars}\nSetting: {self.env}\n"
                f"{self.one_each.capitalize()}. no split panels, no grid, no borders, " + self.neg_img + "\n",
                encoding="utf-8")
            return seg, self._image([str(self.odir / f"panel_{i+1:02d}.jpg"), *self.sheets, *self.setting], pf, out)

        with wl.patched_config(wl.image_settings(self.w)):
            with ThreadPoolExecutor(max_workers=6) as ex:
                for seg, st in ex.map(one, ids or self.segs):
                    print(seg, st, flush=True)

    # ---------- 5. videos ----------
    def write_video_prompts(self):
        s, T = self.spec, self.spec["segment_seconds"]
        for seg, d in s["segments"].items():
            body = (f"{self.style}, {self.w.fmt['ratio']}, {T}s.\n\n@image1 is the first frame of the video: {d['recap']}. "
                    f"{self.defs}\nSetting: {self.env}\n\n")
            for i, (a, b, act, audio) in enumerate(d["shots"], 1):
                lines = dialogue_only(audio)
                body += f"Shot {i} ({a}–{b}s): {act}\n" + (f"{lines}\n\n" if lines else "\n")
            (self.pdir / f"{seg}.txt").write_text(body + self.vid_rules + "\n" + self.w.neg_video + "\n", encoding="utf-8")

    def videos(self, ids):
        self.write_video_prompts()
        for seg in ids or self.segs:
            for attempt in (1, 2):
                ok, msg = wl.gen_video(self.w, self.keyframe(seg), self.pdir / f"{seg}.txt", self.spec["segment_seconds"],
                                       self.odir / f"{seg}.mp4", self.ldir)
                print(seg, f"attempt {attempt}", msg, flush=True)
                if ok or "paid" in msg:  # submitted = paid: recover with resume_video_task.py, never re-submit
                    break

    # ---------- 6. stitch ----------
    @staticmethod
    def probe(p):
        j = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                                "stream=codec_type,r_frame_rate:format=duration", "-of", "json", str(p)]))
        n, d = next(x for x in j["streams"] if x["codec_type"] == "video")["r_frame_rate"].split("/")
        return float(j["format"]["duration"]), float(n) / float(d)

    def film_path(self):
        return self.odir / f"{self.spec['name']}_film.mp4"

    def stitch(self):
        clips = [self.odir / f"{seg}.mp4" for seg in self.segs]
        missing = [c.name for c in clips if not c.exists()]
        if missing:
            sys.exit(f"missing segments: {missing}")
        inputs, parts = [], []
        for i, c in enumerate(clips):
            dur, fps = self.probe(c)
            a = 1 / fps if i else 0.0
            b = dur - (6 / fps if i < len(clips) - 1 else 0.0)
            inputs += ["-i", str(c)]
            parts.append(f"[{i}:v]trim={a:.4f}:{b:.4f},setpts=PTS-STARTPTS,scale=1280:720,setsar=1,fps={fps:g}[v{i}];"
                         f"[{i}:a]atrim={a:.4f}:{b:.4f},asetpts=PTS-STARTPTS,aresample=48000[a{i}];")
        cat = "".join(f"[v{i}][a{i}]" for i in range(len(clips))) + f"concat=n={len(clips)}:v=1:a=1[v][a]"
        subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", "".join(parts) + cat, "-map", "[v]",
                        "-map", "[a]", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(self.film_path())], check=True)
        print(self.film_path(), self.probe(self.film_path()))

    # ---------- 4. page ----------
    @staticmethod
    def data_uri(p, max_side=1600):
        if not Path(p).exists():
            return ""
        im = Image.open(p).convert("RGB")
        im.thumbnail((max_side, max_side))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

    def page(self):
        s, T = self.spec, self.spec["segment_seconds"]
        e = html.escape
        film = self.film_path()
        film_html = (f'<section><h2>Film <small>{len(self.segs) * T}s · {self.w.fmt["ratio"]} · {self.w.fmt["resolution"]}</small></h2><video controls preload="metadata" '
                     f'src="output/{film.name}"></video></section>') if film.exists() else ""
        segs = ""
        for k, seg in enumerate(self.segs):
            d = s["segments"][seg]
            panels = [(i, p) for i, p in enumerate(s["panels"]) if p["seg"] == seg]
            figs = "".join(f'<figure><img src="{self.data_uri(self.odir / f"panel_{i+1:02d}.jpg", 800)}" alt="panel {i+1}">'
                           f'<figcaption><b>Panel {i+1}</b> {e(p["beat"])}</figcaption></figure>' for i, p in panels)
            kf = self.data_uri(self.keyframe(seg))
            kf_html = f'<figure class="kf"><img src="{kf}" alt="{seg} keyframe"><figcaption><b>{seg} first frame</b> (full resolution)</figcaption></figure>' if kf else ""
            shots = "".join(f"<li><b>{a}–{b}s</b> {e(act)} <span class=au>{e(au)}</span></li>" for a, b, act, au in d["shots"])
            segs += (f'<section><h2>{seg} <small>{k*T}–{(k+1)*T}s</small></h2><div class="row">{kf_html}{figs}</div>'
                     f'<ol class="shots">{shots}</ol><textarea data-seg="{seg}" placeholder="Notes for {seg}: dialogue, action or first-frame changes…"></textarea></section>')
        notes = "".join(f"<li>{e(n)}</li>" for n in s.get("review_notes", []))
        notes_html = f"<section><h2>Review notes</h2><ul>{notes}</ul></section>" if notes else ""
        page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(s['title'])} Storyboard</title><style>
:root{{--bg:#f7f7f4;--card:#fff;--ink:#22252a;--muted:#6b7078;--line:#e3e3de;--accent:#3f7d6e}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#16181b;--card:#202327;--ink:#e8e8e6;--muted:#9a9ea5;--line:#33373c;--accent:#7cc4b0}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif}}
main{{max-width:1200px;margin:0 auto;padding:24px 16px 64px}}h1{{margin:0 0 4px;font-size:26px}}.sub{{color:var(--muted);margin:0 0 20px}}
section{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:0 0 18px}}h2{{margin:0 0 10px;font-size:18px}}
h2 small{{color:var(--muted);font-weight:400;margin-left:6px}}.row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}}
figure{{margin:0}}img,video{{width:100%;border-radius:8px;display:block}}img{{cursor:zoom-in}}video{{background:#000}}
figcaption{{font-size:13px;margin-top:6px}}.kf figcaption b{{color:var(--accent)}}.shots{{margin:12px 0 0;padding-left:18px;font-size:14px}}
.au{{color:var(--muted)}}textarea{{width:100%;margin-top:10px;min-height:42px;border:1px solid var(--line);border-radius:8px;background:transparent;color:var(--ink);padding:8px;font:inherit}}
dialog{{border:0;padding:0;background:transparent;max-width:96vw}}dialog img{{max-height:90vh;width:auto;max-width:96vw;cursor:zoom-out}}dialog::backdrop{{background:rgba(0,0,0,.8)}}
</style></head><body><main><h1>{e(s['title'])}</h1>
<p class="sub">{e(self.w.name)} · {self.cols}×{self.rows} storyboard ({self.cols*self.rows} panels) · {len(self.segs)} segments × {T}s · each segment's first frame is redrawn at full resolution from its first panel. Click any image to enlarge.</p>
{film_html}__DECIDE__<section><h2>{self.cols}×{self.rows} storyboard <small>one Seedream image</small></h2><img src="{self.data_uri(self.grid_img, 2400)}" alt="storyboard grid"></section>
{notes_html}{segs}</main><dialog id="z"><img id="zi" alt=""></dialog><script>
const z=document.getElementById('z'),zi=document.getElementById('zi');
document.querySelectorAll('main img').forEach(i=>i.onclick=()=>{{zi.src=i.src;z.showModal()}});z.onclick=()=>z.close();
</script>__FEEDBACK__</body></html>"""
        page = page.replace("__DECIDE__", DECIDE_HTML).replace("__FEEDBACK__", FEEDBACK_JS.replace(
            "/*STORY*/{}", json.dumps({"name": s["name"], "title": s["title"], "out_dir": s["out_dir"], "segments": self.segs},
                                    ensure_ascii=False)))
        p = self.out / "storyboard.html"
        p.write_text(page, encoding="utf-8")
        pagenav.stamp(self.w, p)
        print(p)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    st = Story(sys.argv[1])
    step, ids = sys.argv[2], sys.argv[3:]
    wl.require(STEP_DEPS.get(step, wl.GROUPS), st.w)
    if step == "preview":
        st.grid(); st.crops(); st.keyframes(ids); st.page()
    else:
        {"grid": st.grid, "crops": st.crops, "keyframes": lambda: st.keyframes(ids), "page": st.page,
         "videos": lambda: st.videos(ids), "stitch": st.stitch}[step]()
