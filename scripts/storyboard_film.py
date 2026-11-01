"""Long take (1–2 min) from one keyframe: storyboard first, then video segments stitched into one film.

One story spec (JSON) drives everything:
  1. grid       one Seedream image: a COLSxROWS storyboard of panels (3x3 = 9 panels by default)
  2. crops      cut the grid into panels (gutters auto-detected)
  2b. panels N  redraw single panels as finished frames and put them back into the sheet (no new sheet)
  2c. continue S2  after the previous segment is rendered: its clip's last frame becomes S2's first frame and panel,
                so the cut is continuous (the frame is cleaned once by Seedream: a raw video frame can be refused by
                the video model as a "real person")
  3. keyframes  each segment's first panel redrawn at the world's keyframe size (panel crop + sheets + location +
                the pictures of the props the segment shows)
  4. page       storyboard.html: grid, keyframes, segment plan, review buttons, the film when present
  5. videos     one Seedance first-frame clip per segment (paid: only after the user approved the storyboard)
  6. stitch     ffmpeg join with the V-6 trim (last 6 frames of each clip, first frame of the next)
  assets        lists the film's copies of its characters, scene and props (assets/, made by every step: one film
                is drawn from one version of each; --refresh takes the canon's newer pictures)

Usage:  python storyboard_film.py <story.json> <step> [segment ids...]
        steps: grid | crops | panels N.. | continue S2.. | keyframes | page | videos | stitch | assets | preview (= grid crops keyframes page)
        --refresh  copy again the canon pictures that were redrawn since this film copied them

Spec fields: name, title, out_dir (relative to the world folder), grid {cols, rows, size}, segment_seconds (default:
the world's), location (a Setting.md location key), cast (optional, default the world's main cast), setting_ref
(optional image, default the location picture), close_scene (optional Setting.md scene key: a close view of the
same place, the room reference of close-up frames), props (optional Setting.md prop keys the whole film shows),
prop_rule (optional, episode-only props), canon_props (optional, true = paste the full props block), panels[cols*rows]{seg, beat, fix?}, segments{S1..}{recap, shots[[a, b, action,
audio], ...]}, review_notes (optional).

Style, characters, the location and the recurring props are NOT in the spec: they are read from the world's canon
(Identities.md, Setting.md) on every run, so every film stays consistent. A recurring prop is found in the panels and
shots by name (worldlib `props_named`) as well as in `props`: its picture goes to the grid and to the keyframe of every
segment that shows it, and its own look into the prompts, so it stays the same object in every frame and clip.
"""
import base64
import html
import io
import hashlib
import json
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _world import pagenav, wl  # noqa: E402
from keyframes import frame_props, props_line, setting  # noqa: E402

# Dependencies each step needs (Dependencies.md); checked before any third-party import so a missing one
# returns the DEPENDENCY ERROR message instead of a traceback.
STEP_DEPS = {"grid": ("python", "image", "world"), "crops": ("python",), "keyframes": ("python", "image", "world"),
             "page": ("python",), "videos": ("python", "video", "world"), "stitch": ("python", "ffmpeg"), "panels": ("python", "image", "world"),
             "continue": ("python", "image", "ffmpeg", "world"),
             "preview": ("python", "image", "world"), "assets": ("python",)}
REFRESH = "--refresh" in sys.argv
# Seedance 2.5 reference limits: images in one request (the first frame included) and seconds of voice clips together.
MAX_REF_IMAGES, MAX_AUDIO_S = 9, 15

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
        # Recurring props: the spec's own plus every canon prop the panels and shots name, each with its picture.
        self.props = frame_props(w, s.get("props"), *self.texts(), s.get("prop_rule"))
        self.env = self.env_for(self.props)
        self.defs = w.get("video-defs") + " " + w.get("voice", "")
        self.vid_rules = w.get("video-rules") + "\n" + w.get("audio")
        # The film's own copies of the canon pictures it is drawn from (assets/, see asset()); every step uses these.
        self.adir = self.out / "assets"
        mf = self.adir / "assets.json"
        self.manifest, self.changed = (json.loads(mf.read_text(encoding="utf-8")) if mf.is_file() else {}), []
        self.sheets = [str(self.asset("characters", c, w.sheet(c))) for c in self.cast]
        ref = w.p(s["setting_ref"]) if s.get("setting_ref") else w.location_image(s["location"])
        self.setting = [str(self.asset("scenes", "setting_ref" if s.get("setting_ref") else s["location"], ref))] \
            if ref.is_file() else []
        # Close view of the same place (optional `close_scene`, a Setting.md scene key): the room reference of close-ups.
        close = s.get("close_scene")
        if close and close not in w.locations():
            raise SystemExit(f"spec 'close_scene' must be a Setting.md scene, one of: {', '.join(w.locations())}")
        cimg = w.location_image(close) if close else None
        self.close_setting = [str(self.asset("scenes", close, cimg))] if cimg and cimg.is_file() else []
        self.prop_pics = {k: self.asset("props", k, w.prop_image(k)) for k in self.props}
        # The cast's designed voices (my-world voices.py), so the page lets the user hear who speaks.
        self.voices = {c: self.asset("voices", c, w.p(f"_asset/voices/{c}.wav")) for c in self.cast}
        self.opening_frame()
        self.save_manifest()
        if self.changed:
            print("note: redrawn in the canon since this film copied them (the film keeps its copies so its segments "
                  f"never mix two versions): {'; '.join(self.changed)}. To take the new pictures, run the step again "
                  "with --refresh, then redraw the grid and keyframes.", flush=True)

    # ---------- assets ----------
    def asset(self, kind, key, src):
        """This film's copy of a canon picture: assets/<kind>/<key>.png, made on first use and recorded in
        assets/assets.json (where it came from, its hash). Once copied it stays, even when the canon picture is redrawn,
        until --refresh: one film is drawn from one version of each character, scene and prop."""
        src = Path(src)
        if not src.is_file():
            return src
        dst = self.adir / kind / f"{key}{src.suffix}"
        name, sha = f"{kind}/{dst.name}", hashlib.sha1(src.read_bytes()).hexdigest()[:12]
        rec = self.manifest.get(name)
        if dst.is_file() and rec and rec["sha1"] != sha and not REFRESH:
            self.changed.append(f"{name} (canon {rec['from']})")
            return dst
        if not dst.is_file() or not rec or rec["sha1"] != sha:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            self.manifest[name] = {"from": wl.rel(src, self.w.root), "sha1": sha,
                                   "copied": datetime.now().isoformat(timespec="seconds")}
        return dst

    def save_manifest(self):
        if self.manifest:
            self.adir.mkdir(parents=True, exist_ok=True)
            (self.adir / "assets.json").write_text(json.dumps(self.manifest, indent=1, ensure_ascii=False),
                                                   encoding="utf-8")

    def opening_frame(self):
        """The film's opening frame (the first segment's first frame, often an approved keyframe) as an asset: every
        later first frame keeps its room, desk, props and light. None until that frame exists."""
        kf = self.keyframe(self.segs[0])
        return self.asset("frames", f"{self.segs[0]}_first_frame", kf) if kf.is_file() else None

    def last_frames(self):
        """The last frame of every rendered segment, as an asset (assets/frames/<seg>_last_frame.jpg): what the next
        segment starts from (`continue`) and what the page shows under Assets. Taken again when the clip is newer."""
        if not shutil.which("ffmpeg"):
            return
        for seg in self.segs:
            clip, dst = self.odir / f"{seg}.mp4", self.adir / "frames" / f"{seg}_last_frame.jpg"
            if not clip.is_file() or (dst.is_file() and dst.stat().st_mtime >= clip.stat().st_mtime):
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.08", "-i", str(clip), "-frames:v", "1",
                            "-q:v", "2", str(dst)], check=True)
            self.manifest[f"frames/{dst.name}"] = {"from": wl.rel(clip, self.w.root),
                                                   "sha1": hashlib.sha1(dst.read_bytes()).hexdigest()[:12],
                                                   "copied": datetime.now().isoformat(timespec="seconds")}
        self.save_manifest()

    def list_assets(self):
        for name, rec in sorted(self.manifest.items()):
            print(f"{name:32} from {rec['from']}  ({rec['copied']})")

    def assets_html(self):
        """The page section that shows what the film is drawn from, by kind: pictures, segment frames, voices."""
        kinds = {"characters": "Characters", "scenes": "Scenes", "props": "Props",
                 "frames": "Frames <small>the film's opening frame and the last frame of each rendered segment</small>",
                 "voices": "Voices <small>each character's designed voice</small>"}
        rows = ""
        for kind, title in kinds.items():
            figs = ""
            for n in sorted(n for n in self.manifest if n.split("/")[0] == kind and (self.adir / n).is_file()):
                src = f'{html.escape(wl.rel(self.adir / n, self.out))}?v={self.manifest[n]["sha1"]}'  # never from cache
                key = n.split("/", 1)[1].rsplit(".", 1)[0]
                if kind == "voices":
                    label = self.w.char_name(key) if key in self.w.chars else key
                    figs += (f'<figure class="voice"><figcaption>{html.escape(label)}</figcaption>'
                             f'<audio controls preload="none" src="{src}"></audio></figure>')
                else:
                    figs += (f'<figure><img src="{src}" alt="{html.escape(n)}"><figcaption>'
                             f'{html.escape(key.replace("_", " "))}</figcaption></figure>')
            if figs:
                rows += f'<h3>{title}</h3><div class="assets">{figs}</div>'
        return (f'<section><h2>Assets <small>this film\'s copies of what it is drawn from (assets/)</small></h2>'
                f'{rows}</section>') if rows else ""

    # ---------- helpers ----------
    def texts(self, seg=None):
        """The words of the film, or of one segment: panel beats and fixes, recaps, shot actions."""
        s = self.spec
        out = [p["beat"] + " " + p.get("fix", "") for p in s["panels"] if seg in (None, p["seg"])]
        for k, d in s["segments"].items():
            if seg in (None, k):
                out += [d.get("recap", "")] + [sh[2] for sh in d["shots"]]
        return out

    def seg_props(self, seg):
        return frame_props(self.w, self.spec.get("props"), *self.texts(seg))

    def env_for(self, props):
        """Setting text: the location and its rules, then the props shown (only their own looks: the whole props
        list pasted into a prompt makes the model draw all of them, so canon_props is opt-in)."""
        s, w = self.spec, self.w
        line = w.get("props") if s.get("canon_props") else props_line(w, props)
        return " ".join(filter(None, (setting(w, s["location"], self.cast), line, s.get("prop_rule"))))

    @staticmethod
    def is_close(text):
        """A close shot, by the words of its beat: close-up, MCU, CU, close view, over the shoulder."""
        return bool(re.search(r"close[- ]?up|close view|close shot|\b(MCU|CU|ECU)\b|over [\w' ]{0,20}shoulder", text or "", re.I))

    def setting_items(self, close=None):
        """The place: the set, and its close view when the spec has `close_scene`. close=None gives both (the grid),
        True the close view alone (a close-up frame), False the set alone."""
        wide = [{"path": p, "note": "the setting to keep consistent"} for p in self.setting]
        near = [{"path": p, "note": "a close view of the same place: the desk, shelves, lamp and wall to keep in close-ups"}
                for p in self.close_setting]
        if close is None:
            return wide + near
        return (near or wide) if close else wide

    def cast_named(self, text):
        """The cast members a beat names (key, name, label or kind), so a frame gets only their sheets: a sheet passed
        for someone who is not in the frame draws them in anyway."""
        t = (text or "").lower()
        def named(c):
            ch = self.w.chars[c]
            terms = {c, ch.get("name", ""), ch.get("label", "").replace("the ", ""), ch.get("kind", "")}
            return any(x and re.search(rf"\b{re.escape(x.lower())}\b", t) for x in terms)
        return [c for c in self.cast if named(c)]

    def chars_for(self, cast):
        """The characters text and count rule for a frame that shows only `cast`: their own parts of the canon
        `characters` block ("Name: …"), exactly one of each, and none of the others."""
        names = {c: self.w.chars[c].get("name", c) for c in self.cast}
        starts = sorted((self.chars.find(f"{n}:"), c) for c, n in names.items() if self.chars.find(f"{n}:") >= 0)
        parts = {c: self.chars[a:(starts[k + 1][0] if k + 1 < len(starts) else None)].strip()
                 for k, (a, c) in enumerate(starts)}
        text = " ".join(parts.get(c, "") for c in cast) or self.chars
        others = [self.w.kind(c) for c in self.cast if c not in cast]
        rule = self.w.one_each(cast) if cast else "no characters"
        return text, rule + (f"; no {', no '.join(others)} anywhere in the frame" if others else "")

    def ref_items(self, props, close=None, cast=None):
        return ([{"path": p, "note": f"the character sheet of {self.w.char_label(c)}", "label": self.w.char_label(c),
                  "pack": True} for c, p in zip(self.cast, self.sheets) if cast is None or c in cast]
                + self.setting_items(close)
                + [{"path": self.prop_pics[k], "note": f"the {k.replace('_', ' ')} prop: copy its look exactly, not its size (the picture is a close-up); draw it at the size the scene gives"}
                   for k in props])

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
        # A segment whose first frame is given beforehand (an approved keyframe copied to S1_keyframe.jpg): its panel is
        # drawn as that picture, so the storyboard and the film start the same way.
        given = [(self.first_panel(seg), self.keyframe(seg)) for seg in self.segs if self.keyframe(seg).is_file()]
        items = self.ref_items(self.props) + [{"path": kf, "note": f"the finished frame of panel {i + 1}: draw panel {i + 1} "
                                               "as exactly this picture"} for i, kf in given]
        refs, notes = wl.fit_refs(items, self.out / "work" / "grid")
        ref_note = "; ".join(notes) + ". Use the sheets for identity only."
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
        print("grid", self.run_image(refs, pf, self.grid_img, s["grid"]["size"]))

    # ---------- 2. crops ----------
    def boxes(self, g):
        """Each panel's box (x0, y0, x1, y1) on the storyboard sheet, from its white gutters."""
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
        return [(cols[i % self.cols][0], rows[i // self.cols][0], cols[i % self.cols][1], rows[i // self.cols][1])
                for i in range(self.cols * self.rows)]

    def put_panel(self, g, box, i, pic):
        """Replace panel i on the sheet and as its crop with a finished picture."""
        pic = Image.open(pic).convert("RGB").resize((box[2] - box[0], box[3] - box[1]), Image.LANCZOS)
        g.paste(pic, box[:2])
        pic.save(self.odir / f"panel_{i+1:02d}.jpg", quality=95)
        g.save(self.grid_img, quality=95)

    def crops(self):
        g = Image.open(self.grid_img).convert("RGB")
        boxes = self.boxes(g)
        for i, box in enumerate(boxes):
            g.crop(box).save(self.odir / f"panel_{i+1:02d}.jpg", quality=95)
        # A first frame given beforehand replaces its panel, on the sheet and as the crop, so the page shows one picture.
        for seg in self.segs:
            kf, i = self.keyframe(seg), self.first_panel(seg)
            if kf.is_file():
                self.put_panel(g, boxes[i], i, kf)
        print("crops", self.cols * self.rows, "boxes", boxes)

    # ---------- 2c. continue from the previous clip ----------
    def continue_from_clip(self, ids):
        """Each segment in ids starts from the last frame of the rendered segment before it. The frame is grabbed with
        ffmpeg, then redrawn once by Seedream keeping it exactly (a raw, upscaled video frame was refused by the video
        model as "may contain real person"), and becomes the segment's keyframe and its first panel. Draw the
        segment's other panels as edits of it (`panels N` with "same camera as panel N" in the beat)."""
        g = Image.open(self.grid_img).convert("RGB")
        boxes = self.boxes(g)
        for seg in ids:
            prev = self.segs[self.segs.index(seg) - 1] if self.segs.index(seg) else None
            clip = self.odir / f"{prev}.mp4" if prev else None
            if not clip or not clip.is_file():
                sys.exit(f"{seg}: the segment before it has no rendered clip ({clip.name if clip else 'none'})")
            raw, out = self.out / "work" / f"{seg}_from_{prev}.png", self.keyframe(seg)
            raw.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.08", "-i", str(clip), "-frames:v", "1",
                            "-vf", "scale=" + self.w.fmt["keyframe_size"].replace("x", ":") + ":flags=lanczos", str(raw)],
                           check=True)
            if out.exists():  # keep the frame it replaces
                (self.odir / "v1").mkdir(exist_ok=True)
                shutil.move(out, self.odir / "v1" / f"{seg}_keyframe_{datetime.now():%Y%m%d_%H%M}.jpg")
            pf = self.pdir / f"{seg}_keyframe.txt"
            pf.write_text(f"{self.style}. Image 1 is a finished frame of the animated film: keep it EXACTLY - same camera, "
                          "framing, room, furniture, light, colours, every character's place and pose, every prop. Only "
                          "render it as a crisp, clean stylised animated film frame: smooth stylised shading, sharp edges, "
                          "no photographic grain or blur. Change nothing else.\n", encoding="utf-8")
            print(seg, self.run_image([raw], pf, out, None), flush=True)
            i = self.first_panel(seg)
            self.put_panel(g, boxes[i], i, out)

    # ---------- 2b. one panel redrawn ----------
    def redraw_panels(self, nums):
        """Redraw single panels (1-based numbers) as finished frames, without rolling the whole sheet again: each is
        drawn from its beat with the same references as a first frame (the opening frame for the room, the set or its
        close view, the sheets, the segment's props), saved as panel_NN_full.jpg and put back into the sheet."""
        s, opening = self.spec, self.opening_frame()
        self.save_manifest()

        def one(n):
            i = int(n) - 1
            p, out = s["panels"][i], self.odir / f"panel_{i+1:02d}_full.jpg"
            if out.exists():
                wl.archive(out, self.w, "storyboard")
            props, fix = self.seg_props(p["seg"]), p.get("fix", "")
            close = self.is_close(p["beat"] + " " + fix)
            same = ([{"path": opening, "note": "the film's opening frame: keep exactly its room, furniture, desk, lamp, small "
                      "props, colours and light; do NOT copy its camera framing, and do NOT copy who is in it"}]
                    if opening and i != self.first_panel(self.segs[0]) and not close else [])  # a wide frame pulls close-ups wide
            cast = self.cast_named(p["beat"])
            items = [*same, *self.ref_items(props, close, cast)]
            if close and self.close_setting:  # a close shot is built on the close view itself, as image 1
                # The close view already holds the place and its props at their size: the prop pictures only lend their
                # look ("not their size"), and nothing else is passed, so the framing stays the set's.
                items = ([{"path": self.close_setting[0], "note": "the finished set picture this frame is built on: keep "
                           "it EXACTLY - the same camera viewpoint and framing, furniture, lamp, wall, the small props at "
                           "their exact size and place, colours and light - and only add the characters the scene names"}]
                         + [x for x in items if x.get("pack")]
                         + [{"path": self.prop_pics[k], "note": f"the {k.replace('_', ' ')} prop: copy only its look; it "
                             "keeps the small size and place it has in image 1"} for k in props])
            refs, notes = wl.fit_refs(items, self.out / "work" / f"panel_{i+1:02d}")
            pf = self.pdir / f"panel_{i+1:02d}.txt"
            chars, rule = self.chars_for(cast)
            pf.write_text(f"{self.style}. {self.w.ratio_words} composition, full-bleed, no borders: one finished frame of "
                          f"a short film.\nReferences: {'; '.join(notes)}. Use them for identity.\n"
                          f"Scene: {p['beat']} {fix}\nCharacters: {chars}\nSetting: {self.env_for(props)}\n"
                          f"{rule[0].upper() + rule[1:]}. no split panels, no grid, no borders, " + self.neg_img + "\n",
                          encoding="utf-8")
            return i, self._image([str(r) for r in refs], pf, out)

        with wl.patched_config(wl.image_settings(self.w)):
            with ThreadPoolExecutor(max_workers=6) as ex:
                done = list(ex.map(one, nums))
        g = Image.open(self.grid_img).convert("RGB")
        boxes = self.boxes(g)
        for i, st in done:
            full = self.odir / f"panel_{i+1:02d}_full.jpg"
            if full.exists():
                self.put_panel(g, boxes[i], i, full)
            print(f"panel {i+1}", st, flush=True)

    # ---------- 3. keyframes ----------
    def keyframes(self, ids):
        s = self.spec

        def one(seg):
            out = self.keyframe(seg)
            if out.exists():
                return seg, "exists"
            i = self.first_panel(seg)
            fix = s["panels"][i].get("fix", "")
            props = self.seg_props(seg)
            # Later segments keep the room, desk, props and light of the film's opening frame (its copy in assets/),
            # but take their framing and who is on screen from their own panel.
            same = ([{"path": opening, "note": "the film's opening frame: keep exactly its room, furniture, desk, lamp, small "
                      "props, colours and light; do NOT copy its camera framing, and do NOT copy who is in it"}]
                    if seg != self.segs[0] and opening else [])
            refs, notes = wl.fit_refs([{"path": self.odir / f"panel_{i+1:02d}.jpg", "note": "the storyboard panel"},
                                       *same, *self.ref_items(props, self.is_close(s["panels"][i]["beat"] + " " + fix))],
                                      self.out / "work" / seg)
            pf = self.pdir / f"{seg}_keyframe.txt"
            pf.write_text(
                f"{self.style}. {self.w.ratio_words} composition, full-bleed, no borders.\n"
                "Image 1 is a small storyboard panel: recreate exactly its composition, camera framing, character poses, "
                "setting and lighting as one finished full-resolution frame with crisp detail. "
                + "; ".join(notes[1:]) + ". Use them for identity.\n"
                f"Scene: {s['panels'][i]['beat']} {fix}\nCharacters: {self.chars}\nSetting: {self.env_for(props)}\n"
                f"{self.one_each.capitalize()}. no split panels, no grid, no borders, " + self.neg_img + "\n",
                encoding="utf-8")
            return seg, self._image([str(r) for r in refs], pf, out)

        todo = list(ids or self.segs)
        with wl.patched_config(wl.image_settings(self.w)):
            if self.segs[0] in todo:  # the opening frame first: the later ones are drawn against it
                print(*one(self.segs[0]), flush=True)
                todo.remove(self.segs[0])
            opening = self.opening_frame()
            self.save_manifest()
            with ThreadPoolExecutor(max_workers=6) as ex:
                for seg, st in ex.map(one, todo):
                    print(seg, st, flush=True)

    # ---------- 5. videos ----------
    def speakers(self, seg):
        """The cast members who speak in a segment, in order of their first line ({Dog (whisper): "…"} → the
        character whose canon tag is <Dog>)."""
        by_tag = {self.w.chars[c].get("tag", "").strip("<>").lower(): c for c in self.cast}
        found = [by_tag.get(t.lower()) for sh in self.spec["segments"][seg]["shots"]
                 for t in re.findall(r"\{\s*([\w ]+?)\s*[(:]", sh[3] or "")]
        return list(dict.fromkeys(c for c in found if c))

    def video_refs(self, seg):
        """What a segment's video sees besides its first frame (@image1): the sheets of the cast it names, the place
        (its close view too when a shot is close), the pictures of the props it shows, and the voices of who speaks.
        Returns (images, image notes, audios, voice notes). Voices are cut to fit MAX_AUDIO_S together."""
        d, texts = self.spec["segments"][seg], self.texts(seg)
        cast = self.cast_named(" ".join(texts + [sh[3] or "" for sh in d["shots"]]))
        close = any(self.is_close(sh[2]) for sh in d["shots"])
        items = self.ref_items(self.seg_props(seg), None if close else False, cast)
        items = [i for i in items if Path(i["path"]).is_file()][:MAX_REF_IMAGES - 1]
        images = [i["path"] for i in items]
        notes = [f"@image{n} is {i['note'].replace('copy its look exactly, not its size (the picture is a close-up); draw it at the size the scene gives', 'copy only its look; it keeps the small size and place it has in @image1')}"
                 for n, i in enumerate(items, 2)]
        voiced = [c for c in self.speakers(seg) if Path(self.voices.get(c, "")).is_file()]
        audios, vnotes = [], []
        each = MAX_AUDIO_S / len(voiced) if voiced else 0
        for n, c in enumerate(voiced, 1):
            src = Path(self.voices[c])
            length = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                                    "-of", "csv=p=0", str(src)], text=True))
            if length > each:  # the voices together must fit the model's audio limit
                cut = self.out / "work" / "voices" / f"{c}_{each:.1f}s.wav"
                cut.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-t", f"{each:.2f}", str(cut)], check=True)
                src = cut
            audios.append(src)
            vnotes.append(f"@audio{n} is the voice of {self.w.chars[c].get('tag', c)} ({self.w.char_name(c)}): "
                          f"{self.w.chars[c].get('tag', c)} speaks every line in exactly this voice")
        return images, notes, audios, vnotes

    def write_video_prompts(self):
        s, T = self.spec, self.spec["segment_seconds"]
        self.vrefs = {}
        for seg, d in s["segments"].items():
            props = self.seg_props(seg)
            images, notes, audios, vnotes = self.vrefs[seg] = self.video_refs(seg)
            refs = ("References (identity and look only; the framing, places and poses come from @image1): "
                    + "; ".join(notes) + ".\n") if notes else ""
            voices = ("Voices: " + "; ".join(vnotes) + ". Keep the words of the script, not the words in the voice "
                      "clips.\n") if vnotes else ""
            # With references the clip is All-Reference: @image1 is not locked as the opening frame, so the words do it.
            opening = ("@image1 is the first frame of the video" if not (images or audios) else
                       "The video opens exactly on @image1, its first frame: the same camera, framing, room, light, and "
                       "every character's place and pose, with nothing added, so it cuts on from the previous clip")
            body = (f"{self.style}, {self.w.fmt['ratio']}, {T}s.\n\n{opening}: {d['recap'].rstrip('.')}. "
                    f"{self.defs}\n{refs}{voices}Setting: {self.env_for(props)}\n\n")
            for i, (a, b, act, audio) in enumerate(d["shots"], 1):
                lines = dialogue_only(audio)
                body += f"Shot {i} ({a}–{b}s): {act}\n" + (f"{lines}\n\n" if lines else "\n")
            (self.pdir / f"{seg}.txt").write_text(body + self.vid_rules + "\n" + self.w.neg_video + "\n", encoding="utf-8")

    def videos(self, ids):
        self.write_video_prompts()
        for seg in ids or self.segs:
            for attempt in (1, 2):
                images, _, audios, _ = self.vrefs[seg]
                ok, msg = wl.gen_video(self.w, self.keyframe(seg), self.pdir / f"{seg}.txt", self.spec["segment_seconds"],
                                       self.odir / f"{seg}.mp4", self.ldir, images, audios)
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
        self.last_frames()
        s, T = self.spec, self.spec["segment_seconds"]
        e = html.escape
        film = self.film_path()
        film_html = (f'<section><h2>Film <small>{len(self.segs) * T}s · {self.w.fmt["ratio"]} · {self.w.fmt["resolution"]}</small></h2><video controls preload="metadata" '
                     f'src="output/{film.name}?v={int(film.stat().st_mtime)}"></video></section>') if film.exists() else ""

        def clip_html(seg):
            """The segment's rendered clip (?v=: a re-render is never played from the browser cache), with links to
            the earlier renders kept in output/render_*/."""
            clip = self.odir / f"{seg}.mp4"
            if not clip.is_file():
                return ""
            older = "".join(f' <a href="{e(wl.rel(p, self.out))}">{e(p.parent.name.replace("_", " "))}</a>'
                            for p in sorted(self.odir.glob(f"render_*/{seg}.mp4")))
            return (f'<figure class="clip"><video controls preload="metadata" src="output/{clip.name}?v={int(clip.stat().st_mtime)}">'
                    f'</video><figcaption><b>{seg} clip</b> {self.probe(clip)[0]:.1f}s'
                    + (f' · earlier:{older}' if older else "") + '</figcaption></figure>')

        # The video prompts exactly as the next `videos` would submit them (written now; voice cuts need ffmpeg).
        if shutil.which("ffmpeg"):
            self.write_video_prompts()

        def prompt_html(seg):
            """A read-only popup with the segment's full video prompt and the pictures and voices sent with it."""
            pf = self.pdir / f"{seg}.txt"
            if not pf.is_file():
                return "", ""
            images, _, audios, _ = getattr(self, "vrefs", {}).get(seg, ([], [], [], []))
            sent = [("@image1", self.keyframe(seg))] + [(f"@image{n}", p) for n, p in enumerate(images, 2)]                 + [(f"@audio{n}", p) for n, p in enumerate(audios, 1)]
            mode = ("All-Reference: @image1 is the first frame by the prompt's words" if images or audios else
                    "first frame: @image1 is the literal opening frame")
            refs = "".join(f"<li><b>{t}</b> {e(wl.rel(Path(p), self.out))}</li>" for t, p in sent)
            dlg = (f'<dialog class="vp" id="vp-{seg}"><div class="vpbox"><header><b>{seg} video prompt</b> '
                   f'<small>read-only · what the next render of {seg} submits · {e(mode)}</small>'
                   f'<button type="button" class="vpx" aria-label="Close">✕</button></header>'
                   f'<h3>Sent with it</h3><ul class="vprefs">{refs}</ul><h3>Prompt '
                   f'<small>prompt/{seg}.txt · {len(pf.read_text(encoding="utf-8"))} characters</small></h3>'
                   f'<pre>{e(pf.read_text(encoding="utf-8"))}</pre></div></dialog>')
            return f'<button type="button" class="vpbtn" data-vp="vp-{seg}">Video prompt</button>', dlg

        segs, dialogs = "", ""
        for k, seg in enumerate(self.segs):
            d = s["segments"][seg]
            panels = [(i, p) for i, p in enumerate(s["panels"]) if p["seg"] == seg]
            figs = "".join(f'<figure><img src="{self.data_uri(self.odir / f"panel_{i+1:02d}.jpg", 800)}" alt="panel {i+1}">'
                           f'<figcaption><b>Panel {i+1}</b> {e(p["beat"])}</figcaption></figure>' for i, p in panels)
            kf = self.data_uri(self.keyframe(seg))
            kf_html = f'<figure class="kf"><img src="{kf}" alt="{seg} keyframe"><figcaption><b>{seg} first frame</b> (full resolution)</figcaption></figure>' if kf else ""
            shots = "".join(f"<li><b>{a}–{b}s</b> {e(act)} <span class=au>{e(au)}</span></li>" for a, b, act, au in d["shots"])
            btn, dlg = prompt_html(seg)
            dialogs += dlg
            segs += (f'<section><h2>{seg} <small>{k*T}–{(k+1)*T}s</small> {btn}</h2>{clip_html(seg)}<div class="row">{kf_html}{figs}</div>'
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
figcaption{{font-size:13px;margin-top:6px}}.assets{{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px}}.assets img{{background:#fff;object-fit:contain;aspect-ratio:4/3}}.assets small,h3 small{{color:var(--muted);font-weight:400}}h3{{font-size:15px;margin:14px 0 8px}}.voice audio{{width:100%;margin-top:6px}}.clip{{margin:0 0 12px}}.clip video{{max-width:960px}}.clip a{{color:var(--accent)}}.kf figcaption b{{color:var(--accent)}}.shots{{margin:12px 0 0;padding-left:18px;font-size:14px}}
.au{{color:var(--muted)}}textarea{{width:100%;margin-top:10px;min-height:42px;border:1px solid var(--line);border-radius:8px;background:transparent;color:var(--ink);padding:8px;font:inherit}}
dialog{{border:0;padding:0;background:transparent;max-width:96vw}}dialog img{{max-height:90vh;width:auto;max-width:96vw;cursor:zoom-out}}dialog::backdrop{{background:rgba(0,0,0,.8)}}
.vpbtn{{margin-left:10px;font:13px system-ui,sans-serif;padding:3px 10px;border:1px solid var(--accent);border-radius:999px;background:transparent;color:var(--accent);cursor:pointer;vertical-align:2px}}
dialog.vp{{width:min(980px,96vw)}}.vpbox{{background:var(--card);color:var(--ink);border-radius:12px;padding:16px;max-height:90vh;overflow:auto}}
.vpbox header{{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}}.vpbox header small{{color:var(--muted);flex:1}}.vpx{{border:0;background:transparent;color:var(--ink);font-size:18px;cursor:pointer}}
.vprefs{{margin:0;padding-left:18px;font-size:13px}}.vprefs b{{color:var(--accent)}}.vpbox pre{{white-space:pre-wrap;word-break:break-word;font:13px/1.5 ui-monospace,Consolas,monospace;background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:12px;margin:0;user-select:text}}
</style></head><body><main><h1>{e(s['title'])}</h1>
<p class="sub">{e(self.w.name)} · {self.cols}×{self.rows} storyboard ({self.cols*self.rows} panels) · {len(self.segs)} segments × {T}s · each segment's first frame is redrawn at full resolution from its first panel. Click any image to enlarge.</p>
{film_html}__DECIDE__<section><h2>{self.cols}×{self.rows} storyboard <small>one Seedream image</small></h2><img src="{self.data_uri(self.grid_img, 2400)}" alt="storyboard grid"></section>
{self.assets_html()}{notes_html}{segs}</main>{dialogs}<dialog id="z"><img id="zi" alt=""></dialog><script>
const z=document.getElementById('z'),zi=document.getElementById('zi');
document.querySelectorAll('main img').forEach(i=>i.onclick=()=>{{zi.src=i.src;z.showModal()}});z.onclick=()=>z.close();
document.querySelectorAll('.vpbtn').forEach(b=>b.onclick=()=>document.getElementById(b.dataset.vp).showModal());
document.querySelectorAll('dialog.vp').forEach(d=>{{d.onclick=ev=>{{if(ev.target===d)d.close()}};d.querySelector('.vpx').onclick=()=>d.close()}});
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
    step, ids = sys.argv[2], [a for a in sys.argv[3:] if a != "--refresh"]
    wl.require(STEP_DEPS.get(step, wl.GROUPS), st.w)
    if step == "preview":
        st.grid(); st.crops(); st.keyframes(ids); st.page()
    else:
        {"grid": st.grid, "crops": st.crops, "keyframes": lambda: st.keyframes(ids), "page": st.page,
         "videos": lambda: st.videos(ids), "stitch": st.stitch, "assets": st.list_assets,
         "panels": lambda: st.redraw_panels(ids), "continue": lambda: st.continue_from_clip(ids)}[step]()
