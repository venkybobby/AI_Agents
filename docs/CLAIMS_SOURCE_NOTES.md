# Claims Source Notes

This repository encodes claims-demo reference data from public CMS/OIG/AMA-aligned guidance into local SQLite fixtures for deterministic tests.

## Encoded locally

- OIG LEIE exclusion lookup supports provider identifiers by type (`NPI`, `EIN`, `SSN`) in the reference repository contract.
- NCCI PTP edits use `modifier_indicator` semantics:
  - `0`: modifier bypass is not allowed.
  - `1`: bypass may be allowed when an appropriate NCCI-associated modifier is present.
- NCCI bypass modifiers are stored in `ncci_bypass_modifiers`, not hardcoded in Python.
- Office/outpatient E/M timing ranges for `99202`-`99215` are stored in `em_requirements`.
- SSN and EIN masking is handled before log/display use.

## Production boundary

The 837 parser is a demo adapter, not a certified X12 translator. Production should replace `ai_agents.domains.claims_837` with an EDI gateway/parser and preserve the normalized claim contract consumed by the claims domain.

OIG/CMS/AMA reference data should be loaded through governed ingestion jobs in production. The local SQLite seed exists only for repeatable demos and CI.

## Reference URLs

- CMS NCCI FAQ Library: https://www.cms.gov/medicare/coding-billing/national-correct-coding-initiative-ncci-edits/medicare-ncci-faq-library
- CMS modifier 59/X{EPSU} guidance: https://www.cms.gov/files/document/mln1783722-proper-use-modifiers-59-xe-xp-xs-xu.pdf
- OIG LEIE exclusions: https://oig.hhs.gov/exclusions/
- OIG LEIE quick tips: https://oig.hhs.gov/exclusions/leie-quick-tips-instructions/
- AMA E/M overview: https://www.ama-assn.org/practice-management/cpt/cpt-evaluation-and-management
