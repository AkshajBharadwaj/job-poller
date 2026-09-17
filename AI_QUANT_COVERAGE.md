# AI and quant expansion — September 17, 2026

Scope: US software/ML internships and quant software/developer internships.
This is a curated expansion, not a claim to cover every startup or guarantee
compensation. No salary floor is applied: postings often omit compensation.
Quant trader/researcher-only roles and full-time roles remain excluded.

## Deployed additions

AI: Thinking Machines Lab, Reflection AI, Cartesia, Poolside, World Labs,
Factory, Fireworks AI, Liquid AI, Luma AI, Prime Intellect, Augment Code.

Quant: Aquatic Capital Management, Headlands Technologies, DV Trading,
Da Vinci Trading, Engineers Gate.

All 16 passed `careers.check <names> --twice` in an isolated staging package
on the actual VM before deployment; no jobs.db was created by the checks.
Two deterministic tests cover city normalization, geography, SWE versus
trading/research exclusion, and Prime Intellect's generic technical internship.
The live service discovers 355 adapters; the timer remains active. New
adapters participate from the next process start, without restarting a running
poll or changing the user's existing database.

No changes to shared watch.py, feeds.py, filters.py or existing adapters.
The new quant helper is opt-in, not a global location/filter change.
Fireworks uses its current Ashby board, not the stale Greenhouse endpoint.
Prime Intellect's technical 'Internship' is tagged FullTime by Ashby;
its adapter uses explicit internship titles to avoid silently dropping it.

## Current matches — apply directly

Initial company polling baselines these without emailing old postings.

- [Aquatic — Software Engineer Intern, Summer 2027](https://job-boards.greenhouse.io/aquaticcapitalmanagement/jobs/8489233002)
- [DV Trading — AI Engineer Intern, Summer 2027](https://job-boards.greenhouse.io/dvtrading/jobs/4732429005)
- [DV Trading — Software Developer Intern, DV Equities, Summer 2027](https://job-boards.greenhouse.io/dvtrading/jobs/4733138005)
- [DV Trading — Software Engineer Intern, DV Commodities, Summer 2027](https://job-boards.greenhouse.io/dvtrading/jobs/4719119005)
- [Prime Intellect — technical Internship](https://jobs.ashbyhq.com/PrimeIntellect/486b3511-7128-46f9-93a5-fc1d748d8852)

Other additions returned no matching internships. Their boards were checked
separately to distinguish real nonempty boards from broken/empty feeds.
No matching role today is not evidence a firm has never recruited interns.

## Known gaps / not counted as coverage

- Citadel and Citadel Securities: public careers pages return HTTP 403 from
  the VM. No broken adapter installed. Their official sites do list US SWE
  internships; manually check https://www.citadel.com/careers/open-opportunities/
  and https://www.citadelsecurities.com/careers/open-opportunities/.
- Essential AI and Mistral: candidate ATS feeds returned zero total jobs;
  need current official-feed verification before adding.
- Hebbia: candidate Greenhouse feed returned 404; not installed.
- This expansion does not repair unrelated pre-existing failing adapters
  (e.g. SIG) or audit every existing company's filtering.

The VM has additional pre-existing adapters not present in this local
checkout. Deployment copied only the validated new directories/helper and
preserved all VM-only adapters, secrets, logs, and database state.
