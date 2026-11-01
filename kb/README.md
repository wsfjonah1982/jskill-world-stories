# Knowledge Base: Task Feedback

Raw lessons from real world-stories tasks (keyframes, short footage, long takes), one file per task, with the
world-specific details removed. The main sources are the story files under `_tasks/` (idea.json, scripts,
story.json, the pasted page feedback), the world's journal and `world.md`, and the reviewer's notes.
This folder is for maintainers. `SKILL.md` does not load it.

**This is the raw record, and it only grows.** Entries are never trimmed or rewritten; only the Status column
changes. How a project records story lessons, how the story part of a bundle becomes an entry here, and when a
lesson may go into the skill are in [`../Learning.md`](../Learning.md). In short: everything is recorded, and a
lesson is promoted only when it is a tool failure, a model limit or a paid render a free check could have saved, or
when its theme shows up in two or more worlds (see **Trends**).

## Adding an entry

File name: `YYYY-MM-DD_<task-type>.md` (for example `2026-10-30_long-take.md`). Copy the template below.
Remove everything that identifies the world: character, place and prop names, story titles and quoted lines.
Keep what generalises: the kind of story, the art style family, what went wrong, and how it was fixed.

```markdown
---
date: YYYY-MM-DD
task: keyframes | short footage | long take | revise
style: 3D cartoon | flat matte 3D | 2D | custom
source: story files | journal | world.md | review | user feedback | session review
world_entry: my-world kb/YYYY-MM-DD_<task-type>.md (when the same bundle wrote one)
---

## Context
One or two lines: what kind of story, how long (keyframes, segments), what the session did.

## Lessons
| # | Theme | Lesson | Origin | Status |
|---|---|---|---|---|
| 1 | storyboard | … | user correction / agent observation / tool failure | adopted / candidate / rejected |
```

**Theme** is a short tag from the Trends table (reuse an existing one when it fits). **Origin** shows how much to
trust a lesson: a *user correction* counts for more than an *agent observation*; a *tool failure* is a reproducible
bug. **Status:** `adopted` (name the file), `candidate` (waiting for more evidence) or `rejected` (say why).

## Index

| Date | Task | Style | Lessons | Adopted |
|---|---|---|---|---|
| 2026-10-30 | [long take, 1 min, 3 segments](2026-10-30_long-take.md) | flat matte 3D, dark | 9 | 1 |
| 2026-10-31 | [props not matching their pictures](2026-10-31_props-consistency.md) | 3D cartoon | 6 | 6 |
| 2026-11-01 | [long take at one desk, continuity and close shots](2026-11-01_long-take-continuity.md) | 3D cartoon | 23 | 15 |

## Trends

One row per theme: which entries report it (by date and lesson number) and where it stands. A theme seen in two or
more worlds pointing the same way is ready to review for promotion.

| Theme | Entries (date #lesson) | Worlds | State |
|---|---|---|---|
| storyboard (what reaches the grid) | 2026-10-30 #1 | 1 | candidate |
| story-consistency (a story's lines agree) | 2026-10-30 #2 | 1 | candidate |
| frame-refs (a frame declares its assets; check before paying) | 2026-10-30 #3 #4 #5; 2026-10-31 #4; 2026-11-01 #1 #2 #23 | 2 | warning for props adopted; characters invented after the first frame now in 2 worlds (paid both times): per-panel `refs` and the refusal ready to review; SKILL.md names the workaround |
| checks (how the word check reads) | 2026-10-30 #6 #7; 2026-11-01 #16 | 2 | candidate (different points: no shared fix yet) |
| episode-props (props keep their designed look) | 2026-10-30 #8 #9; 2026-10-31 #1 #2 #3; 2026-11-01 #13 | 2 | canon props adopted (2 worlds); one-off episode props (#8) candidate |
| prop-size (props drawn at their reference picture's scale) | 2026-10-31 #6; 2026-11-01 #14 | 1 | adopted: prompt wording, then my-world `place_prop.py` (model limit) |
| assets (a film is drawn from its own copies) | 2026-10-31 #5; 2026-11-01 #11 | 1 | adopted (user request) |
| continuity (segments cut together) | 2026-11-01 #3 #4 #8 #9 #22 | 1 | #3 #4 #9 adopted (user corrections); #8 #22 candidate |
| close-views (close shots at one spot) | 2026-11-01 #5 #6 | 1 | adopted: `close_scene`, `panels` |
| cast-per-frame (only who is in the frame) | 2026-11-01 #7 | 1 | adopted |
| model-limits (refusals, what a model will not do) | 2026-11-01 #10 #17 | 1 | adopted: `continue` cleans a video frame; videos use All-Reference with sheets, props and voices |
| revisions (a fix undoes an approved detail) | 2026-11-01 #12 | 1 | candidate |
| timing (rendered timing vs the script) | 2026-11-01 #15 | 1 | candidate |
| review-page (what the storyboard page shows before paying) | 2026-11-01 #18 #19 #20 | 1 | adopted (user requests) |
| canon-in-prompts (a canon block contradicting the scene) | 2026-11-01 #21 | 1 | candidate |
