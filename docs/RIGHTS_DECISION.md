# Project rights decision memo (#3)

Status: **OWNER_DECISION_REQUIRED**. This memo records the current evidence and
the decision needed to finish #3. It does not select a license, grant reuse
permission, change ownership, or claim a legal review has happened.

The root README states that the repository has no project LICENSE. The public
default branch has no root license. Dependency notices apply to their own code;
they do not establish this project's license. See [GitHub's licensing guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository).

## Owner decision to record

Choose one distribution intent: open source, source available, all rights
reserved, or pause public distribution. Record the selected text/version,
effective date, covered repository commit, copyright holders, permitted use,
modification, redistribution, deployment, commercial use and contribution terms.
Do not assume those rights for provider-derived data or third-party assets.

| Material | Evidence now | Decision/provenance still required |
| --- | --- | --- |
| Original code | No project license/grant recorded | Distribution model, license text, copyright holders |
| Original documentation | No separate grant recorded | Same license as code or a separately stated text license |
| Figma/design/exported assets | Asset rights not established by the code repository | Original creator, template/font/icon provenance, permitted exports/reuse |
| Screenshots | Software license does not settle all depicted content | Author, third-party content, allowed reuse and redaction |
| Generated fare observations | Observation artifacts are distinct from source code | Provider terms, retention, redistribution and publication rights |
| Third-party-derived metadata | No reviewed data-rights grant recorded | Source, version/date, applicable terms, required attribution |
| Vendored `punitarani/fli` | MIT notice preserved at `third_party/fli/LICENSE.txt` | Preserve notice; separately review provider service/data obligations |
| Other dependencies/fonts/icons | Purposes are listed in `OPEN_SOURCE_STACK.md` | Review exact resolved artifacts and their notices independently |
| Contributions | No contributor license/ownership policy selected | Inbound license/ownership rule and authority to submit changes |
| Deployment/runtime artifacts | No separate license established | Exclude secrets/personal data; decide whether observations may be exported |

`docs/UPSTREAM_FLI.md` records the vendored upstream commit and notice. That
MIT notice applies to the vendored dependency; it does not license original
project code or authorize collecting/redistributing Google Flights observations.
`docs/OPEN_SOURCE_STACK.md` describes dependencies and provider limitations;
it is not a completed legal compliance review.

## Implement after the decision

1. Have the owner record the distribution decision and asset provenance. Obtain
   qualified human review for provider terms or jurisdiction-specific questions
   when needed; record the reviewer/date/scope without publishing personal data.
2. Add the selected root LICENSE/NOTICE text and any distinct documentation/asset
   terms. Align README and CONTRIBUTING wording with that exact decision.
3. Record third-party notices/data-source obligations independently. Do not apply
   a blanket source-code license to runtime observations.
4. Add a repository-contract check for the selected required files and wording.
   Until the selection exists there is no valid selected-license invariant to test.

Human owner/legal review: **NOT_RUN**. Rights to reuse code, assets and provider
data remain unresolved in this memo. This prepared matrix is not issue closure.
