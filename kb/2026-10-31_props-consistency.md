---
date: 2026-10-31
task: keyframes + short footage + long take
style: 3D cartoon
source: user feedback
world_entry: none
---

## Context
A small family world (three characters, ten scenes, six recurring props, each with a picture). The user reported that
stories "many times" drew props that did not match the props designed earlier.

## Lessons
| # | Theme | Lesson | Origin | Status |
|---|---|---|---|---|
| 1 | episode-props | A keyframe got a prop's picture only when its `props` list named it; a prop named only in the beat was drawn from words. Detect canon props by name in the beat and shots and pass their pictures. | user correction | adopted: `keyframes.frame_props`, worldlib `props_named` |
| 2 | episode-props | The long-take grid and segment keyframes never received prop pictures, and the video prompts had no prop text at all. | user correction | adopted: `storyboard_film.py` (grid, keyframes, video prompts per segment) |
| 3 | episode-props | Pasting the whole props list draws every prop; paste only the shown props' own looks (the Recurring props row). | agent observation | adopted: `keyframes.props_line` |
| 4 | frame-refs | A prop a segment shows but its first frame does not hold is drawn from words by the video model. | agent observation | adopted as a warning in `storyboard_film.py videos`; the refusal stays candidate (long-take #4) |
| 5 | assets | A long take should be drawn from one version of each picture: copy the sheets, scene and prop pictures into the task (`assets/`) and keep them when the canon is redrawn. | user correction | adopted: `storyboard_film.py` assets, `--refresh` |
