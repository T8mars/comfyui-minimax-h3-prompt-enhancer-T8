# OpenMOSS prompt-enhancer resources

Original materials: OpenMOSS/MOSS-Image, commit
`c1355e6b1986dfe8fba3c0455783a05899212342`, under Apache-2.0 (see LICENSE).
SKILL.md, references/layout.md and scripts/compile_prompt.py are unchanged
upstream snapshots. Their hashes and original paths are in source.json.
scripts/test_compile_prompt.py is the unchanged upstream regression suite.

T8 adapts the file/tool-agent instructions into an in-memory chat contract in
moss_image_contract.py. It does not execute model-supplied code, call a rendering
service, download weights or claim that every LLM matches the upstream agent.
The T8 project license does not replace the upstream license for these files.
