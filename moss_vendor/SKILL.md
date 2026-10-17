---
name: moss-image-prompt-enhancer
description: Expand an image-generation request into a detailed MOSS-Image caption or spatial layout, and compile a local JSON draft into a ready-to-paste prompt. Use for prompt enhancement, image composition and text placement; this skill does not generate images.
---

# MOSS-Image Prompt Enhancer

Turn the user's idea into a concrete image description. Target GPT-6-family
agents with filesystem and shell tools. The agent makes creative decisions;
the bundled Python tool handles coordinate arithmetic and serialization.
No Echidna service, model API or third-party Python dependency is needed.

## Choose the deliverable

Honor an explicit request for a caption or Layout. Otherwise use a caption for
ordinary scenes, photographs and illustrations. Use Layout when specific text
placement, a poster, several panels, or controlled object relationships would
benefit from bounding boxes. A detailed image does not automatically need Layout.

Preserve the user's subjects, counts, relationships, medium, style, exclusions
and intended visible wording. Resolve ordinary creative gaps yourself; ask only
when a missing decision would materially change the requested image. Do not
invent factual event logistics or specifications as if the user supplied them.

Default to English for descriptive prose, following a requested output language
when given. Preserve visible text verbatim in its original language, including
punctuation, capitalization and requested line breaks. A quoted sentence in an
instruction is not necessarily text to render: distinguish visible wording from
reference material and constraints.

## Develop the image

Describe visible choices: subject and action, relevant appearance, setting,
camera/framing, medium, lighting, materials, palette and mood. Add detail where
it makes the requested image more specific. Avoid redundant quality tags,
unrequested style changes, arbitrary word budgets and invisible process notes.
Keep an explicit minimalist brief minimalist; develop a rich brief without
turning it into a generic title/hero/footer template.
Keep explanations of JSON, bounding-box annotations and conversion steps out of
image-description fields; those are tool instructions, not depicted content.

For designed images, compose the information and imagery together. Establish
reading order, relative prominence, coherent groups and readable text at the
chosen pixels. Write the intended copy rather than placeholders such as
"headline here" or "some explanatory text". Do not import unrelated names,
watermarks or copy from a reference. Use supplied references when useful; outside
research is optional unless needed for factual accuracy or requested by the user.

## Caption

Write a UTF-8 JSON file containing exactly `{"caption":"..."}`. The caption is
cohesive prose, with spatial relations in words and any visible wording quoted
exactly. It may contain paragraphs; do not add coordinates or JSON-layout fields
to a caption just to make it look structured.

## Layout

Read [references/layout.md](references/layout.md) before writing a Layout draft.
Write readable JSON with `summary`, a flat `items` array, concrete `width` and
`height`, `bbox_coord_space="abs"` and `bbox_format="xyxy"`.

**Draft boxes use `[x_min,y_min,x_max,y_max]` in actual pixels, from the canvas
top-left.** Keep x in `0..width` and y in `0..height`. Do not use normalized
coordinates or manually center, reorder or quantize the boxes.

Honor supplied dimensions. With only an aspect ratio, choose compatible pixel
dimensions; without either, use 1024×1024 unless the requested medium suggests
another shape. MOSS-Image dimensions must be positive multiples of 16. Do not
silently change explicit dimensions that are incompatible; surface the conflict.
Use the same width and height in the image-generation workflow.

Use boxes for coherent visible units, splitting only when independent placement
matters. Grouping should preserve content and relationships, not erase them.
Natural occlusion and overlap are allowed. A box is a placement annotation,
not an instruction to draw a border, panel or sticker. Describe appearance in
captions and global treatment in `summary.caption`; let boxes agree with any
spatial descriptions. Keep exact visible strings in text items' `text` fields.

## Compile and deliver

Save the draft to a user-appropriate working directory, then run the tool bundled
beside this SKILL.md. Resolve the script path from the skill location, not the
user's working directory:

```bash
python3 /path/to/moss-image-prompt-enhancer/scripts/compile_prompt.py \
  draft.json --output prompt.txt
```

Use an actual path in the invocation. Keep the editable JSON draft and compiled
output separate. Read the result and check the subject, exact text, intended
geometry and chosen canvas before delivering. Fix validation errors in the draft
and rerun; do not bypass a failed conversion by hand-writing centered JSON.

For captions, the output is plain text. For Layout, it is one physical line of
JSON with flat `items`, integer `abs_centralized` / `yxyx` boxes and no canvas
metadata. The tool encloses fractional pixel edges before subtracting the center,
matching Echidna's generation conversion. It rejects invalid or out-of-bounds
boxes instead of silently clipping them. String newlines are escaped in the JSON
while remaining actual newlines in the decoded text.

Return the ready-to-paste prompt or a link to its file, and retain a link to the
draft when useful for editing. For Layout also state the required width×height
outside the prompt; the model prompt itself does not contain these dimensions.
If showing Layout JSON inline, use the compiled output without reformatting it.
Only the caption or compiled Layout belongs in MOSS-Image's positive prompt.
Creating these files does not submit image generation or publish anything.
