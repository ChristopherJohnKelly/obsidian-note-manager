# PLAN.md — OBSE-P5 Temporal SOA Migration

## Feature Branch
feat/OBSE-P5-temporal-soa-migration

## Steps

| ID  | Name                        | Branch                                         | Depends On      | Status  | PR  | Attempts | Claimed By |
|-----|-----------------------------|------------------------------------------------|-----------------|---------|-----|----------|------------|
| S01 | Monorepo Scaffolding | step/OBSE-P5-S01-monorepo-scaffolding | — | done | #19 | 1 |  |
| S02 | Dummy Vault and Fake LLM | step/OBSE-P5-S02-dummy-vault-fake-llm | S01 | done | #20 | 2 |  |
| S03 | Temporal Test Environment | step/OBSE-P5-S03-temporal-test-environment | S01,S02 | done | #21 | 2 |  |
| S04 | Vault IO Activities | step/OBSE-P5-S04-vault-io-activities | S03 | done | #22 | 0 |  |
| S05 | Git Operations Activities | step/OBSE-P5-S05-git-operations-activities | S03 | done | #23 | 2 |  |
| S06 | LLM Generation Activities | step/OBSE-P5-S06-llm-generation-activities | S03,S04 | done | #24 | 1 |  |
| S07 | ReadVaultWorkflow | step/OBSE-P5-S07-read-vault-workflow | S04,S05 | done | #28 | 9 |  |
| S08 | WriteVaultWorkflow | step/OBSE-P5-S08-write-vault-workflow | S04,S05 | done | #29 | 4 |  |
| S09 | VaultManagerWorkflow | step/OBSE-P5-S09-vault-manager-workflow | S04,S05 | done | #31 | 2 |  |
| S10 | NightWatchmanWorkflow | step/OBSE-P5-S10-night-watchman-workflow | S06,S07,S08 | done | #32 | 1 |  |
| S11 | FilerIngestionWorkflow | step/OBSE-P5-S11-filer-ingestion-workflow | S06,S07,S08 | queued | #— | 1 |  |
| S12 | CopilotSessionWorkflow | step/OBSE-P5-S12-copilot-session-workflow | S06,S07 | review | #35 | 0 |  |
| S13 | GitHub Runner Refactor      | step/OBSE-P5-S13-github-runner-refactor        | S10,S11,S12,S17 | pending  | —   | 0        |            |
| S14 | Copilot UI Refactor         | step/OBSE-P5-S14-copilot-ui-refactor           | S11,S12,S17     | pending  | —   | 0        |            |
| S15 | CI/CD Pipeline              | step/OBSE-P5-S15-ci-cd-pipeline                | S13,S14,S17     | pending  | —   | 0        |            |
| S16 | Production Docker Compose   | step/OBSE-P5-S16-production-docker-compose     | S09,S13,S14,S15,S17 | pending | — | 0       |            |
| S17 | Monorepo Path Hygiene | step/OBSE-P5-S17-monorepo-path-hygiene | — | done | #30 | 1 |  |

## Status Transitions

```
queued ──► in-progress ──► review ──► done
                      └──► failed    (attempts >= 5 or unrecoverable)
review ──► queued           (cc-obsidian rejects; resets for retry)
```

## Notes

- S04, S05 can run in parallel (both depend only on S03)
- S07, S08, S09 can run in parallel (all depend on S04+S05)
- S10, S11, S12 can run in parallel once their dependencies are met
- S13, S14 can run in parallel (both depend on S11+S12+S17; S13 also needs S10)
- S16 is the final integration step; requires all prior steps complete
- S17 is a mechanical hygiene bubble with no upstream dependencies — it can run at any time and only needs to ship before S13/S14 begin. S08 and S09 do NOT depend on S17 (their bubble paths are already correct).
