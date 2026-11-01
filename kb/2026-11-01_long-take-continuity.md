---
date: 2026-11-01
task: keyframes + long take
style: 3D cartoon
source: journal + story files + world.md + session review
world_entry: my-world kb/2026-11-01_night-study-scene.md
---

## Context
A one-minute long take (3 segments of 20 s, a 3x3 storyboard) at one place: a child studying at a desk at night,
with the two pets talking quietly elsewhere in the room. Most of the film is close shots at the desk. Many storyboard
revision rounds (wrong framing in close panels, invented furniture, pets added, props too big); three paid renders
(the whole film twice, then one segment redone to start from the previous clip's last frame).

## Lessons
| # | Theme | Lesson | Origin | Status |
|---|---|---|---|---|
| 1 | frame-refs | Characters a segment brings in after its first frame are invented from words: the last segment started at the desk with no pets, its last shot asked for them, and they came back as two dogs (paid). Describing them in full in that shot ("the one and only cat, …, exactly one cat and one dog") held the count on the next render. | user correction | candidate; second world for 2026-10-30 #3 (ready to review). The skill now says to name such characters in full |
| 2 | frame-refs | A keyframe that already holds the cast must not be the long take's room reference (`setting_ref`): its characters and framing leaked into every other frame. Use the empty set; start S1 from the keyframe by copying it to `S1_keyframe.jpg`. | agent observation | adopted: formats.md (the `setting_ref` example changed) |
| 3 | continuity | When a segment starts from a given picture, its storyboard panel must be that picture, or the page shows two versions of one frame. | user correction | adopted: `grid` and `crops` put given first frames into their panels |
| 4 | continuity | Every later first frame is drawn against the film's opening frame (room, desk, props, light), taking only framing and cast from its own panel, so the segments cut together. | user correction | adopted: `keyframes`, `assets/frames/S1_first_frame.jpg` |
| 5 | close-views | A film with many close-ups at one spot needs a close view of that spot as its own room reference. With only the wide set, close frames invented the surroundings (a desk moved to a window). | user correction | adopted: `close_scene` |
| 6 | close-views | A close panel is built on the close view as image 1 ("keep it exactly, only add the character"), not on a wide frame: the wide frame pulled the framing wide. Extra prop pictures on top made the small props big again; passing them "for look only, keep the size and place they have in image 1" did not. | user correction | adopted: `panels N` |
| 7 | cast-per-frame | A frame gets only the sheets and character text of who is in it, plus "no <kind>" for the others: a sheet passed for an absent character draws them in. | user correction | adopted: `cast_named`, `chars_for` |
| 8 | continuity | When the user says a panel should follow another, draw it as an edit of that panel's picture that changes only what the beat changes. | user correction | candidate (done by hand with `panels` and a "same camera as panel N" beat) |
| 9 | continuity | A segment redone after the one before it was rendered should start from that clip's last frame: the cut becomes seamless and the user preferred it. Its other panels are drawn as edits of that frame. | user correction | adopted: `continue S2` |
| 10 | model-limits | An upscaled frame grabbed from a rendered clip was refused by the video model as "may contain real person" (400, before submitting, not charged). One image-model pass keeping the frame exactly ("only render it as a clean stylised frame") passed first time. | tool failure | adopted (model limit): `continue` cleans the frame |
| 11 | assets | When a canon picture the film uses is redrawn at the user's request, refresh the film's copy at once (`--refresh`); the page also needs cache-busting, or the browser keeps showing the old picture. | user correction | adopted: `--refresh`, `?v=<sha1>` |
| 12 | revisions | Fixing one detail in a redraw can undo approved ones (a toy size fixed, the book moved off the desk). Re-check every earlier note on each new take, and give small props an explicit count ("exactly one of each, no other toys"). | user correction | candidate |
| 13 | episode-props | Two small props side by side fuse into one object (the card one holds appears in the other's hands) unless the beat says "two separate toys" and which one holds what. | agent observation | candidate |
| 14 | prop-size | Small props kept coming back at the scale of their close-up pictures in keyframes and panels, after "copy the look, not the size" (2026-10-31 #6). They were made right by placing them in the scene pictures after drawing (my-world `place_prop.py`) and building close frames on those pictures. | user correction | adopted (model limit): my-world `place_prop.py`, SKILL.md |
| 15 | timing | A 20 s segment with a 4 s silent walk and then four lines came back with the first line at 0 s and the last lines run together: the video model shortens silent openings when the dialogue is long. | agent observation | candidate |
| 16 | checks | The transcription heard a whispered "Shh." as "Psst." A whispered or very short line needs one listen by the user; the word check alone cannot clear it. | agent observation | candidate |
| 17 | model-limits | The video model saw only the first frame and the words: no character sheet, prop picture or voice clip. Seedance 2.5 takes reference images and voice clips, but refuses them together with a first frame (400 before the task, free). All-Reference mode with the first frame as @image1 and "the video opens exactly on @image1" opened on nearly the same picture (a slight reframe), kept the scripted timing including a silent opening, and voiced every line; one paid test. | user request + tool failure | adopted: `videos` passes sheets, scene, props and voices (`generate_video_multimodal.py`); confirmed on all 3 segments (both small props held in every close shot, which first-frame renders lost; every line on time); short footage (`short_footage.py`) still first-frame only |
| 18 | review-page | The user could not see what a film was made from beyond the pictures: they asked for the last frame of each rendered segment and the characters' voices on the storyboard page. | user request | adopted: Assets groups Frames (last frames taken from the clips by `page`) and Voices (players) |
| 19 | review-page | Only the stitched film was on the page; the user asked for each segment's clip there too, to judge a segment before paying for another. | user request | adopted: a clip player per segment, links to earlier renders in `output/render_N/`, `?v=` so a re-render is never played from cache |
| 20 | review-page | The user asked to see the full prompt each clip will submit, read-only, before rendering. Showing it with the list of pictures and voices sent (and the mode) made the gap in #17 visible: before, a video saw no sheet, prop or voice. | user request | adopted: **Video prompt** popup per segment, rebuilt by `page` |
| 21 | canon-in-prompts | The world's style block says "soft warm daylight" and is pasted into every prompt, night scenes included; the night set and first frame kept the renders at night, but the words contradict them. | agent observation | candidate (the style block should not carry the light; the user did not ask to change it) |
| 22 | continuity | A segment started from the previous clip's last frame (#9) depends on that clip: when the previous segment is re-rendered, the next one opens on the old ending (here the dog lay elsewhere) and must be `continue`d and rendered again. | agent observation | candidate (`continue` could warn when the previous clip is newer than the keyframe) |

## Not here
- The night set, the lamp-light colour rule, the small animal's size and the small-props cut-out are world lessons:
  my-world `kb/2026-11-01_night-study-scene.md`.
- How the user wants study scenes staged is a preference in the world's journal.
