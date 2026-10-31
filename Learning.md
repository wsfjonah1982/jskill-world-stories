# Learning: how world-stories gets better from its use

The skill improves in two loops:

1. **Recording**, in every project where stories are made: the agent writes down what the story taught, and at the
   end it goes into the project's task-learning bundle.
2. **Improving**, in this repo: a maintainer turns the story part of each bundle into a `kb/` entry, watches for
   themes that repeat across worlds, and changes the skill only when the evidence is there.

world-stories works inside a world built with my-world, so the two skills share **one journal and one bundle per
project**. my-world's `Learning.md` describes the journal record and the bundle. This file adds what is specific
to stories.

---

## Part 1 – Recording (every usage, in the user's project)

### Where it goes

| What | Where (inside `_world/`) |
|---|---|
| One record per turn that taught something | `_reference/journal/journal.jsonl`, with `"skill": "world-stories"` |
| What this story decided, its known issues | the task folder (`_tasks/<date>_<slug>/`) and `world.md` (session log) |
| The exported bundle | `_reference/learning/<YYYY-MM-DD>_<task>.zip` (one per task, shared with my-world) |

### What to record

Write a journal record (format in my-world's `Learning.md`) whenever one of these happens:
- **The user revises a keyframe, script or storyboard,** with the pasted feedback note as `said`.
- **A render came back wrong:** which segment, what drifted (a character invented, a prop changed, the language
  switched), and whether it was paid for. Paid failures matter most. Record the cost: "one segment re-rendered".
- **A fix did not take:** the words were changed but the picture stayed (a `fix` that never reached the grid).
- **A check missed something, or flagged something that was fine.**
- **The cause was in the world, not the story:** a character or object without a picture, a canon block too vague.
  Mark it `"skill": "my-world"`: it is the world that needs changing.

### What the bundle adds for stories

Besides what my-world's `Learning.md` lists, a story task adds:

```
story/<K>.idea.json        the idea with its keyframes
story/<K>.script.json      short-footage scripts, when there are some
story/long_<K>.story.json  the long-take spec (panels, refs, segments)
skills/world-stories/…     only the world-stories files this project changed
```

Text only: no keyframes, clips or films. Note the paid renders and their outcome in the README instead.

### Rules while recording

- Don't edit this skill's files in a user's project unless the user asks. If they do, the changed files go into
  the bundle with the journal record that says why.
- Don't fix a world problem inside a story (a description pasted into one prompt): record it for my-world, and fix
  the canon with my-world.

---

## Part 2 – Improving (maintainers, in this repo)

### Taking in a bundle

Bundles arrive once per project and are opened on the my-world side (its `_learning/` folder, see my-world's
`Learning.md`). The story part is then split off:

1. Write one entry here, `kb/YYYY-MM-DD_<task>.md` with **the same date** as the my-world entry, and its
   `world_entry` field pointing there. The template is in `kb/README.md`.
2. Record every story lesson, minor ones included, each with a theme, an origin and a status. Remove what
   identifies the world (names, places, story titles, quoted lines).
3. A story lesson whose cause is in the world goes to my-world's entry, with a one-line pointer here.
4. When the bundle carries a changed copy of this skill's files, `diff` them against this repo and note in the
   lesson what the other project built. Don't merge it until the lesson is adopted.
5. Update the Index and the Trends table in `kb/README.md`.

`kb/` only grows. Entries are never trimmed or rewritten; later only the Status column changes.

### When a lesson goes into the skill

Promote a lesson only when:
- it is a **reproducible tool failure or a hard model limit**, or a **paid render lost to a gap the tool could have
  caught** for free (a check that would have stopped it before paying), or
- its **theme is in two or more entries from different worlds**, pointing the same way.

Everything else stays `candidate`. A `rejected` lesson says why.

### How to promote

1. Choose the most enforceable place: a check in a script (before any paid step) first, then the spec format
   (`references/formats.md`), then a rule in `SKILL.md`.
2. If another project already built it (in a bundle), start from their diff, but rewrite it to fit this repo and
   keep it generic.
3. Test on a scratch copy of a world and story, never a real one. Never run a paid step to test.
4. Mark the lesson `adopted: <file>` in **every** entry that mentions it, update its Trends row, and commit the fix
   and the kb update together.

### Reviewing the kb

Each time an entry is added, read the Trends table: a theme now in two worlds is reviewed and decided; a theme that
splits keeps both sides noted; an adopted lesson that later entries contradict is marked `revisit`.

---

## Further reading

- `kb/README.md` has the entry template, the Index and the Trends table.
- `../my-world/Learning.md` has the journal record format, the bundle, and the world side of the split.
