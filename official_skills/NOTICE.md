# MiniMax Music 3 official Skill resources

`music-caption-rewriter/` is copied from the official
[`MiniMax-AI/MiniMax-Music3`](https://github.com/MiniMax-AI/MiniMax-Music3)
repository at commit `91410fb657c007ae57c60df8240f5ece5be089c7`.

The directory intentionally contains the complete official Skill snapshot:

- `SKILL.md`
- the genre router
- all 18 family indexes
- all 1,000 full caption templates
- the official README and agent metadata

The node follows progressive disclosure. A request reads the router, at most
two selected family indexes, and at most three selected full templates. The
full library is never sent to an LLM in one request.

`SOURCE.json` records the pinned upstream commit, expected counts, and a
normalized content-tree hash used by the repository tests.
