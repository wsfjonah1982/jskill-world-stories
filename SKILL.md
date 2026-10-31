---
name: world-stories
description: >
  Make stories in a "My World" (a world built with the my-world skill: world.json + Identities.md + Setting.md +
  character sheets): from a topic the user gives, design story ideas and keyframes, render them for approval on a
  keyframes page, write timed scripts and dialogue in the characters' voices, then render short footage (one clip)
  or a 1–2 minute long take (storyboard first, then segments stitched into one film), every step consistent with
  the world's canon. Use whenever the user gives a topic, idea or episode for their world/series/characters, asks
  for keyframes, a script, a short clip or a long take, pastes "Copy feedback" JSON from a keyframes or storyboard
  page, or asks to continue, revise or render a story in an existing _tasks/ folder.
---

# World stories

Every story lives in the world folder and takes **everything visual and vocal from the world's canon**: the style,
the characters, the location, the props, the voices and the audio rule are pasted from the `<!-- prompt:... -->`
blocks on every run, and the character sheets, location picture, height chart and prop pictures are passed as
image references. A story file only names a `location`, a `cast`, a camera and what happens. Never describe a
character or a place inside a story file; if the canon is wrong or missing something, fix it with the my-world skill
first (e.g. a new location), then continue.

Needs the **my-world** skill next to this one (or env `MY_WORLD_DIR`); generation and keys come from it. Scripts run
`worldlib` checks themselves; **if one prints `DEPENDENCY ERROR`, stop and give the user the message verbatim**.

Before starting, read the world: `world.json`, `Identities.md`, `Setting.md`, `world.md` (open items, lessons), and
look at the character sheets once.

## The flow — the user approves at every gate

```
topic ─► idea.json (keyframe designs) ─► keyframes.html ─► 👍/👎, short or long ─► approval.json
                                                         │
             short ◄─────────────────────────────────────┴──────────────► long
 script/<K>.json ─► prompt ─► user marks Generate ─► output/<K>.mp4      long_<K>/story.json ─► storyboard.html
                                                                         ─► user approves ─► videos ─► stitch
```

Keyframes and storyboards are cheap previews: render them without asking. **Videos are paid: render one only after
the user marked it Generate / approved the storyboard.**

### 1. Topic → keyframe designs
- Folder `_tasks/<YYYY-MM-DD>_<slug>/`. Write `idea.json` (format in `references/formats.md`): `title`, the topic in
  the user's words, and the keyframes: by default **5 different takes** on the topic (different moments, locations or
  camera angles) unless the user asks for another number (e.g. 10 ideas, one keyframe each).
- Each design: `location` (a key in Setting.md), `cast` (character keys), optional `props` (prop keys; any canon prop the beat names is
  added by name, and every prop shown must have its picture, or the render stops and says so),
  `camera` (`[shot size, angle, movement]`), `beat` (what happens, concrete and visual, one moment). Write beats that
  play to the characters' personalities and the world's humour; respect the world's rules.

### 2. Keyframes → approval
- `python scripts/keyframes.py <idea.json> all` renders every keyframe and writes `keyframes.html`; `--dry-run`
  writes the prompts only. `render K2` redraws one after its design changed (delete the old `output/K2.jpg` first).
- Look at each result yourself before presenting (Read the image): wrong count, sizes, eyes, colours, text in the
  picture → fix the beat or the canon and redraw.
- Run my-world `build_overview.py` so the task appears in the Tasks list, then give the user the `keyframes.html`
  path. The page keeps choices in the browser; the user pastes **Copy feedback** JSON (or saves `approval.json`).
- On pasted feedback: save it as `approval.json` in the task folder, act on each keyframe (notes → change the design
  and redraw; 👎 → leave it), then rebuild the page (`keyframes.py <idea.json> page`).

### 3. Scripts
- Short footage: `script/<K>.json` with timed shots and dialogue (format in `references/formats.md`). Dialogue follows
  each character's voice and speech rules in Identities.md; keep lines short enough to say in the shot.
- `python scripts/short_footage.py <idea.json> prompts [K…]` writes `script/<K>.md` and `prompt/<K>_video.txt` and
  checks the timings; then `keyframes.py <idea.json> page` so the user sees the script on the page and can edit it,
  mark it **Generate**, **Needs changes** or **Draft the script for me**.
- Feedback with an edited script: save it to `script/<K>.json`. With a hand-edited prompt: save it to
  `prompt/<K>_video.txt` and create `prompt/<K>_video.edited` (keeps it from being rebuilt).

### 4. Short footage
- After the user marked it Generate: `python scripts/short_footage.py <idea.json> videos K2` → `output/K2.mp4`
  (Seedance first-frame clip: the approved keyframe is the opening frame). `videos` then runs `check` (free; also
  `short_footage.py <idea.json> check K2` on its own): `output/K2_frames.jpg` (contact sheet) and `output/K2_check.md`
  (audio transcribed with faster-whisper, each scripted line matched with its timing). Read the contact sheet and
  the check, report drift and missing or off-time lines plainly; music still needs one listen by the user.

### 5. Long take (1–2 min)
- For a liked keyframe with a long-take brief (conversation topic, 1 or 2 minutes, lines to include, ending). Best
  when it stays **in one location** and needs lots of dialogue or action that does not fit one clip.
- Write `long_<K>/story.json` (format in `references/formats.md`): 9 panel beats for a 3×3 storyboard, segments of
  `segment_seconds` (1 min = 3 segments of 20s) with timed shots and dialogue, `location`, episode-only props in
  `prop_rule` (describe them once, identically).
- `python scripts/storyboard_film.py long_<K>/story.json preview` draws the storyboard as **one image** (so set,
  props and light agree across the film), crops the panels, redraws each segment's first panel as its keyframe, and
  writes `storyboard.html`. **The film copies what it is drawn from** into `long_<K>/assets/` (character sheets, the
  scene, the pictures of every recurring prop the panels or shots name) and every step uses those copies, so one film
  never mixes two versions of a picture; the page shows them under **Drawn from**. A canon picture redrawn later is
  reported, not taken: `--refresh` takes it (then redraw the grid and keyframes). Put a prop that a segment shows into
  that segment's first panel beat: the video's only image is its first frame (`videos` warns when it is not). Fix a panel by adding `fix` to it and re-running `keyframes S2` (delete the old keyframe).
- After approval (storyboard page **Copy feedback** with `"decision": "approve"`): `videos`, then `stitch`
  (ffmpeg, trims the joins), then `page` → the film is on `storyboard.html`. Rebuild the overview.

### After each session
Update the world's `world.md`: what was made (paths), what the user decided, known issues, pending tasks.
Record what the story taught in the world's journal and, at the end of the task, the bundle (`Learning.md`,
Part 1): every revision, every render that drifted (paid ones first), every fix that did not take.

## Rules
- One location per keyframe and per long take; a scene elsewhere is another keyframe/clip.
- Exactly the cast named; the count and size rules come from the canon — never drop them from a prompt.
- A rule the model keeps breaking in certain scenes (e.g. the leash outdoors) goes into the canon as a scene rule
  (`references/formats.md`), not into each beat; prompts paste it automatically.
- A paid video task that failed after submitting is recovered with my-world `scripts/ark/resume_video_task.py`
  (the error message says how), never resubmitted.
- Pages are plain HTML files opened locally (no server); feedback comes back as pasted JSON.
