# File formats

All `out_dir` paths are relative to the world folder. `<Tag>`s are the characters' `tag` in world.json.

## idea.json — `_tasks/<date>_<slug>/idea.json`

```json
{"title": "Our home and our neighbourhood",
 "idea": "the topic in the user's words",
 "out_dir": "_tasks/2026-10-12_home-neighbourhood",
 "keyframes": [
   {"id": "K1", "title": "Going down in the lift", "location": "lift", "cast": ["mia", "pepper", "biscuit"],
    "props": [], "camera": "[MS, eye level from outside the open lift, static]",
    "beat": "Inside the open lift cabin: Biscuit stands on his hind legs, nose pressed to the blank button panel; the one and only cat, Pepper, sits alone in the back corner giving him a slow blink; Mia holds the handrail, laughing."}]}
```
`cast` uses the characters' `key` in world.json (not their kind or tag) and defaults to every character with
`main` ≠ false. `props` are keys with a picture in `_asset/props/`; a canon prop the beat (or a short script's
shots) names is added automatically (worldlib `props_named`: the key, the Recurring props table name, world.json
`prop_names`). Each shown prop is passed as a picture and described by its own look, never the whole props list.

## Scene rules — world.json `scene_rules` + Setting.md `rule:<name>` blocks

```json
"scene_rules": [{"rule": "leash", "cast": ["biscuit"], "scenes": ["corridor", "lift", "park"]}]
```
When a keyframe, storyboard or video is in one of `scenes` and one of `cast` is on screen, the
`<!-- prompt:rule:<name> -->` block is pasted after the location block automatically (`keyframes.setting()`).
Use it for a rule the model keeps breaking in certain places, instead of repeating it in every beat.

## Keyframes page feedback (pasted, saved as approval.json)

```json
{"page": "keyframes", "idea": "…", "out_dir": "…",
 "keyframes": {
   "K2": {"like": true, "mode": "short", "duration": 15, "note": "…",
          "short": {"decision": "generate" | "revise" | "draft", "note": "…", "script": {…edited script…}, "prompt": "…edited prompt…"}},
   "K4": {"like": true, "mode": "long", "long": {"topic": "…", "minutes": 1, "include": "…", "ending": "…", "notes": "…"}},
   "K5": {"like": false, "note": "…"}},
 "undecided": ["K1"]}
```
- `short.script` present → save it to `script/<K>.json`; `short.prompt` present → save to `prompt/<K>_video.txt` and
  create `prompt/<K>_video.edited`.
- `decision: generate` → render (`short_footage.py videos K…`); `revise` → apply the note, rebuild, show again;
  `draft` → write the first script from the note.

## Short-footage script — `script/<K>.json`

```json
{"title": "Homework on the balcony", "duration": 15,
 "recap": "what the first frame (the approved keyframe) shows",
 "shots": [[0, 5, "[MS, slightly high angle, static] <Girl> tugs at her book under <Cat>; <Cat> stays flat on it.",
            "{Girl (pleading): \"Pepper, please move. I have homework.\"} {Cat (calm): \"I am keeping it warm for you.\"}"],
           [5, 10, "…", "…"], [10, 15, "…", "…"]]}
```
Dialogue always follows the speech rules in the world's Identities.md (accent, languages, banned words); the
example is neutral English. Shots are contiguous from 0 to `duration`; `duration` within the world's short range. Only `{Speaker: "line"}` parts
of the audio cue reach the prompt. Never use `--` (it truncates the prompt).

## Long take — `long_<K>/story.json`

```json
{"name": "k4_neighbourhood_map_1min", "title": "Drawing our neighbourhood map: 1-minute long take",
 "keyframe": "K4", "topic": "the user's brief",
 "out_dir": "_tasks/2026-10-12_home-neighbourhood/long_K4",
 "grid": {"cols": 3, "rows": 3, "size": "2560x1440"}, "segment_seconds": 20,
 "location": "living_room",
 "prop_rule": "Episode props: … described once, identically. It stays the same in every panel.",
 "panels": [{"seg": "S1", "beat": "…"}, … 9 panels, 3 per segment …],
 "segments": {"S1": {"recap": "what S1's first frame shows", "shots": [[0, 6, "…", "{…}"], …]}, "S2": {…}, "S3": {…}},
 "review_notes": ["shown on the storyboard page"]}
```
- 1 minute = 3 segments × 20s (9 panels, 3 per segment); 2 minutes = 6 segments (use a 3×6 or two grids' worth of
  panels: `grid` rows/cols must multiply to the panel count).
- `setting_ref` (optional) replaces the location picture as the setting reference. Use an empty set, never a
  keyframe that holds the cast: its characters and framing leak into every frame (start S1 from the keyframe instead,
  below).
- `storyboard_film.py <spec> panels 2 3` redraws single panels as finished frames and puts them back into the sheet
  (no new sheet): a wide panel is drawn against the opening frame and the set, a close one is built on the
  `close_scene` picture as its base. A panel's `fix` steers this redraw too.
- `close_scene` (optional) is a Setting.md scene key with a close view of the same place (e.g. the desk of a room):
  it is copied into `assets/` (shown under **Assets**), passed to the grid with the set, and used instead of the
  set for a first frame whose panel is a close shot (close-up, MCU, CU, close view, over the shoulder).
- `props` (optional) lists prop keys the whole film shows; props named in panels, recaps or shots are added. Each
  segment's keyframe and video prompt get only the props that segment names.
- `assets/` is made by every step: the film's copies of its character sheets, scene and prop pictures, the cast's
  voices (`voices/<char>.wav`, for listening on the page; the video model does not take them), its opening frame
  (`frames/S1_first_frame.jpg`, which every later first frame is drawn against) and, from `page`, the last frame of
  each rendered segment (`frames/S2_last_frame.jpg`, taken again when the clip is re-rendered), with
  `assets/assets.json` ({"props/owl.png": {"from", "sha1", "copied"}}). The film keeps them when the canon is
  redrawn; `storyboard_film.py <spec> assets` lists them, `--refresh` takes the canon's newer pictures.
- `storyboard_film.py <spec> continue S2` (after S1 is rendered) makes S2 start where S1 ends: the last frame of
  `output/S1.mp4` becomes `S2_keyframe.jpg` and S2's first panel (the old keyframe goes to `output/v1/`). The frame is
  cleaned once by the image model, keeping it exactly: a raw upscaled video frame was refused by the video model as
  "may contain real person". Write that panel's beat as "the last frame of S1, exactly: …", draw the segment's other
  panels with `panels N` as "same camera as panel N", rewrite the recap, then render that segment again.
- To start S1 from the approved keyframe itself, copy `output/<K>.jpg` to `long_<K>/output/S1_keyframe.jpg` before
  `preview` (an existing keyframe is kept).

## Storyboard page feedback

```json
{"page": "storyboard", "story": "…", "out_dir": "…", "decision": "approve" | "revise" | "undecided",
 "note": "general note", "segment_notes": {"S2": "…"}}
```
`approve` → `videos`, `stitch`, `page`. `revise` → change beats/shots (add `fix` to a panel for a first-frame fix),
delete what must be redrawn, `preview` again.
