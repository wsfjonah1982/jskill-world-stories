"""Keyframes for one topic, presented for approval.

The Agent writes `_tasks/<date>_<slug>/idea.json` (the topic plus the keyframe designs); this tool turns each design
into a prompt from the world's canon (Identities.md / Setting.md blocks), renders the keyframes with Seedream at the
world's keyframe size, using the character sheets, the location picture, the height chart and any named prop pictures
as references, and builds `keyframes.html` for the user's decisions.

Usage:  python keyframes.py <idea.json> render|page|all [K1 K3 ...] [--dry-run]
        --dry-run writes the prompts only (no generation). An existing keyframe is kept; delete it to redraw.

idea.json (out_dir is relative to the world folder):
  {"title": "...", "idea": "the topic in the user's words", "out_dir": "_tasks/<date>_<slug>",
   "keyframes": [{"id": "K1", "title": "...", "location": "<Setting.md location key>", "cast": ["<char key>", ...],
                  "props": ["<prop key>"], "camera": "[MS, eye level, static]", "beat": "what happens in this frame"}]}
"""
import html
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _world import pagenav, wl  # noqa: E402

DRY = "--dry-run" in sys.argv
PAGE_TEMPLATE = Path(__file__).resolve().parent / "keyframes_page.html"


def setting(w, location, cast):
    """The location block plus every canon scene rule that applies here: world.json `scene_rules` entries
    ({"rule": name, "scenes": [...], "cast": [...]}) whose scene matches and whose cast is on screen paste their
    `<!-- prompt:rule:<name> -->` block (e.g. the leash rule outdoors)."""
    rules = [w.get("rule:" + r["rule"]) for r in w.cfg.get("scene_rules", [])
             if location in r.get("scenes", []) and set(r.get("cast", cast)) & set(cast)]
    return " ".join([w.get("location:" + location)] + rules)


def frame_props(w, listed, *texts):
    """The recurring props a frame or a clip shows: the ones it lists plus every canon prop its words name
    (worldlib `props_named`). A prop drawn from words alone is re-invented on every roll, so each must have its picture."""
    keys = list(dict.fromkeys([*(listed or []), *w.props_named(*texts)]))
    unknown = [p for p in keys if p not in w.props()]
    missing = [p for p in keys if p not in unknown and not w.prop_image(p).is_file()]
    if unknown or missing:
        sys.exit((f"unknown prop(s) {', '.join(unknown)} (Setting.md has: {', '.join(w.props()) or 'none'}). " if unknown else "")
                 + (f"no picture yet for {', '.join(missing)}: run my-world `world_images.py prop <key>` first." if missing else ""))
    return sorted(keys, key=w.props().index)  # canon order, as keyframes_page.html builds it


def props_line(w, keys):
    """The props text of a prompt: each shown prop's own look (never the whole props list, which draws them all)."""
    if not keys:
        return w.no_props_rule
    return ("Props, each exactly as its reference picture, same shape, colours and size, never redesigned: "
            + "; ".join(w.prop_look(p) for p in keys) + ". No other recurring props.")


def short_props(w, k, sc):
    return frame_props(w, k.get("props"), k["beat"], sc.get("recap"), *(s[2] for s in sc["shots"]))


def short_prompt(w, k, sc):
    """The short-footage video prompt (keyframes_page.html rebuilds it the same way in the browser)."""
    cast = k.get("cast") or w.default_cast()
    body = (f"{w.get('style')}, {w.fmt['ratio']}, {sc['duration']}s.\n\n@image1 is the first frame of the video: "
            f"{sc['recap']}. {w.get('video-defs')} {w.get('voice', '')}\nSetting: {setting(w, k['location'], cast)}\n"
            f"{props_line(w, short_props(w, k, sc))}\n\n")
    for i, (a, b, act, audio) in enumerate(sc["shots"], 1):
        lines = dialogue_only(audio)
        body += f"Shot {i} ({a}–{b}s): {act}\n" + (f"{lines}\n\n" if lines else "\n")
    return body + video_rules(w) + "\n"


def video_rules(w):
    return w.get("video-rules") + "\n" + w.get("audio") + "\n" + w.neg_video


def dialogue_only(audio):
    """Keep only the {Speaker: "line"} parts of a shot's audio cue."""
    import re
    return " ".join(re.findall(r"\{[^}]*\}", audio or ""))


class Idea:
    def __init__(self, path):
        path = Path(path).resolve()
        self.w = wl.World(wl.find_world(path.parent))
        self.spec = json.loads(path.read_text(encoding="utf-8"))
        for k in self.spec.get("keyframes", []):  # "scene" is the name; "location" (older story files) still works
            k.setdefault("location", k.get("scene"))
        self.out = self.w.p(self.spec["out_dir"])
        self.pdir, self.odir, self.ldir = self.out / "prompt", self.out / "output", self.out / "log"
        for d in (self.pdir, self.odir, self.ldir):
            d.mkdir(parents=True, exist_ok=True)

    def cast(self, k):
        return k.get("cast") or self.w.default_cast()

    def refs_and_prompt(self, k):
        w, cast = self.w, self.cast(k)
        props = frame_props(w, k.get("props"), k["beat"], k.get("camera"))
        items = [{"path": w.sheet(c), "note": f"the character sheet of {w.char_label(c)}", "label": w.char_label(c),
                  "pack": True} for c in cast]
        loc_img = w.location_image(k["location"])
        if loc_img.exists():
            items.append({"path": loc_img, "note": "the location: keep its room, furniture, colours and light exactly"})
        if len(cast) > 1 and w.height_chart():
            items.append({"path": w.height_chart(), "note": "the height chart: copy its true relative sizes"})
        items += [{"path": w.prop_image(p), "note": f"the {p.replace('_', ' ')} prop: draw exactly this object"}
                  for p in props]
        if any(not Path(i["path"]).exists() for i in items):  # render() reports what is missing
            refs, notes = [i["path"] for i in items], [f"image {n} is {i['note']}" for n, i in enumerate(items, 1)]
        else:  # over the model's reference limits the sheets share one contact sheet
            refs, notes = wl.fit_refs(items, self.out / "work" / k["id"])
        props = props_line(w, props) + "\n"
        prompt = (f"{w.get('style')}. {w.ratio_words} keyframe for an animated short film, full-bleed.\n"
                  f"References: {'; '.join(notes)}.\n"
                  f"Camera: {k.get('camera', '[MS, eye level, static]')}\n"
                  f"Scene: {k['beat']}\n"
                  f"Characters in this frame: {', '.join(w.char_label(c) for c in cast)}. {w.get('characters')}\n"
                  f"Setting: {setting(w, k['location'], cast)}\n" + props +
                  f"{w.one_each(cast).capitalize()}. {w.neg_image}\n")
        return refs, prompt

    def render(self, ids):
        todo = [k for k in self.spec["keyframes"] if not ids or k["id"] in ids]
        bad = [f"{k['id']}: unknown location '{k['location']}'" for k in todo if k["location"] not in self.w.locations()]
        bad += [f"{k['id']}: unknown character '{c}'" for k in todo for c in self.cast(k) if c not in self.w.chars]
        if bad:
            sys.exit("\n".join(bad) + f"\nlocations: {', '.join(self.w.locations())}; characters: {', '.join(self.w.chars)}")

        def one(k):
            refs, prompt = self.refs_and_prompt(k)
            pf = self.pdir / f"{k['id']}.txt"
            pf.write_text(prompt, encoding="utf-8")
            missing = [str(r) for r in refs if not Path(r).exists()]
            if missing:
                return k["id"], f"missing reference(s): {', '.join(missing)}"
            if DRY:
                return k["id"], f"prompt written ({len(refs)} refs)"
            out = self.odir / f"{k['id']}.jpg"
            if out.exists():
                return k["id"], "exists"
            return k["id"], wl.gen_image(refs, pf, out, self.ldir)

        ctx = wl.patched_config(wl.image_settings(self.w)) if not DRY else _Null()
        with ctx, ThreadPoolExecutor(max_workers=5) as ex:
            for kid, status in ex.map(one, todo):
                print(kid, status, flush=True)

    def page(self):
        """keyframes.html: 👍/👎 per keyframe, short footage or long take for a liked one, the long-take brief, and for
        short footage the script and video prompt to adjust. Plain HTML: the user copies the feedback (JSON) and
        pastes it to the Agent, who applies it."""
        w = self.w
        kfs = []
        for k in self.spec["keyframes"]:
            img = self.odir / f"{k['id']}.jpg"
            made = [("Short footage video", self.odir / f"{k['id']}.mp4"),
                    ("Long-take storyboard", self.out / f"long_{k['id']}" / "storyboard.html")]
            links = [{"label": lab, "href": wl.rel(f, self.out)} for lab, f in made if f.exists()]
            kfs.append({"id": k["id"], "title": k["title"], "location": k["location"], "camera": k.get("camera", ""),
                        "beat": k["beat"], "cast": ", ".join(w.char_name(c) for c in self.cast(k)),
                        "img": wl.rel(img, self.out) if img.exists() else "", "links": links,
                        "setting": setting(w, k["location"], self.cast(k)), "props": k.get("props", []),
                        "short": self.short_data(k["id"])})
        ap = self.out / "approval.json"
        data = {"title": self.spec["title"], "idea": self.spec["idea"], "out_dir": self.spec["out_dir"], "keyframes": kfs,
                "world": w.name, "names": [c["name"] for c in w.chars.values()],
                "format": {"ratio": w.fmt["ratio"], "min": w.fmt["short_min"], "max": w.fmt["short_max"],
                           "options": w.fmt["short_options"], "segment": w.fmt["segment_seconds"]},
                "canon": {"style": w.get("style"), "defs": w.get("video-defs") + " " + w.get("voice", ""),
                          "rules": video_rules(w), "noprops": w.no_props_rule},
                "props": {p: {"terms": w.prop_terms(p), "look": w.prop_look(p)} for p in w.props()},
                "approval": json.loads(ap.read_text(encoding="utf-8")) if ap.is_file() else None}
        page = (PAGE_TEMPLATE.read_text(encoding="utf-8")
                .replace("__TITLE__", html.escape(self.spec["title"]))
                .replace("/*DATA*/", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")))
        p = self.out / "keyframes.html"
        p.write_text(page, encoding="utf-8")
        pagenav.stamp(w, p)
        print(p)

    def short_data(self, kid):
        sf, pf = self.out / "script" / f"{kid}.json", self.pdir / f"{kid}_video.txt"
        return {"script": json.loads(sf.read_text(encoding="utf-8")) if sf.is_file() else None,
                "prompt": pf.read_text(encoding="utf-8") if pf.is_file() else None,
                "prompt_edited": (self.pdir / f"{kid}_video.edited").exists()}


class _Null:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    if len(args) < 2:
        sys.exit(__doc__)
    idea = Idea(args[0])
    step, ids = args[1], args[2:]
    if step in ("render", "all"):
        wl.require(("python", "world") if DRY else ("python", "image", "world"), idea.w)
        idea.render(ids)
    if step in ("page", "all"):
        idea.page()
