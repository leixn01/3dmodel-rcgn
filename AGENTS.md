# Development guidance

- Read README.md, docs/DEVELOPMENT_PLAN.md and docs/ASSET_AUDIT.md before changing the pipeline.
- Prioritize correctness, explicit evidence and a complete review of changes.
- The current sample is STEP AP214 and can be imported by SolidWorks. Do not confuse format support with preservation of native design mates; inspect the imported assembly before deciding which constraints are available.
- Use the existing leixn01/3dmodel-rcgn repository. Keep changes in GitHub rather than delivering repository ZIPs unless explicitly requested.
- Preserve original geometry, source hashes, assembly occurrence paths and raw constraints.
- Do not identify occurrences by filename alone or equate an assembly with a rigid body.
- Keep unknown, candidate, confirmed and conflict states explicit. Never invent limits, mass, coupling, PLC ports or safety conclusions.
- Distinguish geometric clearance, mechanical limits, controller limits and process targets.
- Preserve loops in the canonical constraint graph. Report losses in any tree export.
- Do not commit original CAD, PLC, electrical engineering assets or secrets.
- Keep asset download separate from tests. Unit tests run without network or CAD software.
- Verify meaningful changes with `python -m unittest discover -s tests -v`; CAD import and mechanism validation require separate integration evidence.
- Keep delivered code independently usable; do not call a partial module a complete recognition system.
