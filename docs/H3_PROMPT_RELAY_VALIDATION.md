# Prompt Relay 1.17.0 validation

Date: 2026-09-13. Scope: opt-in authoring in the existing H3 enhancer;
not video generation or a claim of rendered-video quality.

## Real provider checks / 真实 API 测试

Only 贞贞平价小屋 was used for live requests, with
`bytedance/doubao-seed-evolving`. Credentials were supplied on stdin and were
not written to the repository. Synthetic prompts and colour cards were used.

| Case | Elapsed including recovery | Events | Delivery frames | Relay length | Exact six-output recovery |
| --- | ---: | ---: | ---: | ---: | --- |
| 8-second ticket handover, explicit timing and dialogue | 68.22 s | 3 | 192 | 192 | Pass |
| 25.29-second watch repair, automatic weighted timing | 142.12 s | 8 | 607 | 617 | Pass |
| Two reference colour images, 8-second paper movement | 98.78 s | 2 | 192 | 192 | Pass |

An earlier reference-image attempt ended without a complete upstream stream
and failed. A separate repeat with 256×256 colour cards passed. This does not
establish that image dimensions caused the failure. No incomplete response was
counted as success; these timings are observations, not latency guarantees.

## Downstream contract / 下游契约

All three generated results were passed through the reviewed execution
project's actual pure `build_prompt_relay_plan` functions, loaded by AST without
importing its GPU/model components. Every result returned `plan_ready`, with
identical event frame boundaries and aligned length.

Reviewed parser SHA-256:
`50b402e0708c0b7b88690ca2a804af323e72f1ea2bd3dfa251afa38c4df7ab26`.

The adapter workflow's links and types were checked. Its typed
`prompt_relay_events` socket remains disconnected and `timing_mode` is
`seconds`; global/local/time plus the integer length feed the Plan directly.

## Regression scope / 回归范围

- 442 CPU unit/compatibility tests passed, including the optional real-parser
  tests. No local LLM or video model was loaded.
- Normal mode keeps the original enhancement path and output at slot zero.
  New settings and outputs are appended; historical widget prefixes are tested.
- Three cloud routes and local provider parameter flow are covered by mocks;
  only 贞贞平价小屋 has live coverage in this validation.
- Real headless-browser module/DOM tests cover Relay controls, 20 mode toggles
  and stable collapsed height. This is not a full interactive ComfyUI canvas
  acceptance test or a benchmark on every frontend version.
- Format repair is bounded to one additional request and included in request
  diagnostics. Fractional Relay duration is tested separately from normal mode.
- Repository validation includes example workflows, syntax, pinned official
  source hashes, secret/path checks and the Registry package budget.

The original official rules and provider/media paths are reused. The Relay
report explicitly states static validation only. Final motion, transitions,
dialogue timing and visual consistency still need downstream video testing.

## Reproduce

Run `python -m unittest discover -s tests`,
`python tools/verify_repository.py`, and
`python tools/run_frontend_browser_tests.py` in a supported ComfyUI environment.
Set `T8_RELAY_EXECUTION_ROOT` to the reviewed execution project to opt into the
real pure-parser contract tests. The live helper is `h3_relay_live_smoke.py`;
provide the key on stdin, never as a command-line argument. It makes paid API
requests and stores evidence only under the ignored `runtime/` directory.
