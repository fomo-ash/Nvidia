# FixProof submission handoff

## README changes

- Added a concise project introduction and the deliberately induced Kubernetes incident.
- Added explicit pending placeholders for the required demo/test-build URL and public video, rather than fabricated links.
- Added the incident-to-verification flow and a dedicated NVIDIA Nemotron/Nebius Token Factory section.
- Kept implementation status qualified: prior local acceptance is not final-revision acceptance, and a patch is not recovery proof.

## Source and link accuracy check

| Item | Result |
| --- | --- |
| NVIDIA model and provider | Confirmed in `apps/ai/app/config.py`: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, Nebius Token Factory endpoint, selected by the `nebius` provider. |
| Evidence and AI boundaries | Confirmed in `apps/ai/app/llm/nemotron.py`: bounded retained evidence is passed to the model; live responses require valid known evidence citations. |
| Setup and test commands | Cross-checked with `docs/DEVELOPMENT.md`; commands are documented as checks, not as proof that this revision passed them. |
| README documentation links | Checked against tracked files: architecture, security, Discord, kind runbook, demo runbook, and documentation index exist. |
| Root license | Missing. No license was selected because contributor agreement is required. |
| Public demo/test build and video | Not supplied. README contains clear pending placeholders. |

No commands that start infrastructure, run fault injection, or make external calls were run for this documentation update.

## Submission checklist: remaining external assets

- [ ] Publish the code repository with its intended visibility.
- [ ] Agree on and add an approved open-source `LICENSE` at the repository root.
- [ ] Provide a working demo URL or accessible test build, then replace the README placeholder.
- [ ] Publish a public YouTube demo no longer than three minutes, then replace the README placeholder.
- [ ] Prepare the submission description, select the official track, and submit authentic NVIDIA/Nebius feedback.
- [ ] If applicable, document substantial eligible-period changes for a pre-existing project.
- [ ] Run and record current-revision checks before making any claim of final acceptance.

## Implementation handoff

This change is documentation-only. It does not alter application behavior, deployment configuration, model credentials, infrastructure, licensing, or repository publication state. The next owner should add only verified external URLs and a contributor-approved license, then update the checklist with the checks actually run.
