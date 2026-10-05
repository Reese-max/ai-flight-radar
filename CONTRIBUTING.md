# Contribution preparation

Project licensing and contribution ownership are awaiting the owner decision
documented in [the rights memo](docs/RIGHTS_DECISION.md). Public repository access
and this preparation guide do not grant a project license or settle inbound
contribution terms. Preserve dependency copyright/license notices. Do not submit
third-party content without authority to do so.

Keep patches focused and include the relevant offline regression commands and
actual results. Label synthetic fixtures, reviewed official samples and modified
copies distinctly. Do not describe offline tests as live quote calibration or
notification delivery. Changes to collection must preserve provider access
restrictions, budgets, calibration/admission gates and the distinction between
an observed fare and a bookable final price.

Do not commit `.env`, keys/tokens, traveler credentials, personal travel plans,
databases, worker runtime state, private screenshots, raw provider responses or
unlicensed observations. Use disposable test storage and synthetic examples;
keep notification transports and external collection disabled during tests.

Report sensitive security information privately to the repository owner through
an existing trusted contact channel; do not put secret values or exploit traces
containing personal data in a public issue. No dedicated security mailbox or
response SLA is claimed here.
