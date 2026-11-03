# Standing rules for Missing Piece (read before any work)

- **Gates block spend.** Run them in order: S0 → S7. After each gate, stop and report to the owner.
- **No paid collection without the owner's explicit OK.** This covers GPU pods and API calls, including grading.
  **Nothing confirmatory** before S7 (freeze, hashes, OSF posting).
- **No model serving is built here.** Pin the shared pipeline `sae-ethos-pipeline v1.2.0` at commit
  `5ca15f56a71f35d5818d0392f7f3b4acb2d85d1b` (`pins.yaml`).
  - Every run manifest starts with `mp.manifest.header(model, server_start)`.
  - `mp.manifest.check_environment(model)` must pass before any model call.
  - Any pipeline change is a new version and a logged entry in the coordination record.
- **Coordination record:** https://github.com/RandallSPQR/StPT-MP-Coordination. It holds decisions, the protocol spec, the
  evidence schema, pipeline identity, data separation, amendments and deviations, and claim provenance. Prospective
  amendments and post-outcome deviations are logged separately there.
- **Server starts (D14, D22).**
  - Every manifest records the server-start ID.
  - All four cells of a quad run within one start.
  - Blocking by start is mandatory in every Missing Piece analysis.
- **Wording (D20, carry-over 2).**
  - The vote prompt ends with "Reply with exactly one letter, A or B, and nothing else."
  - Non-A/B mass is recorded.
  - No wording is frozen before a held-out comprehension check; if no single wording passes for all models, each model
    gets its own valid set.
- **Roles are never named.** Probes run on forked branches and never return. Live contexts must stay byte-identical with
  and without probes (`mp.isolation`).
- **Banks.** Development and confirmatory banks are separate. No confirmatory scenario is selected on a group outcome.
  Constructed minority-correct profiles are labelled a conditional challenge set and stay in the development bank.
- **No exclusion on any post-treatment measure.** Invalid votes count as non-report votes, with a tipping-point
  analysis.
- **Pilot effect estimates are sealed** (written once, hash in the coordination record, opened only at the owner's
  request).
- **Numbers come only from results files.** Cite the file.
- **Commits.** No model identifiers in commit messages. Use the commit trailers the session's system instructions give.
  No force-push. No PR unless asked.
