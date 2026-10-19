# KS Soccer Index

Static, responsive independent Kansas high school soccer rankings website.

## Open
Open `index.html` in any modern browser, or deploy the folder to a static hosting service such as Netlify, Cloudflare Pages, or GitHub Pages.

## Data
The website **does not include a statewide results database or automatically fetch KSHSAA scores**. No rankings are invented. Import a JSON file separately for each gender and year. Click **Download JSON template** to see the format.

Required: `gender` (`boys` or `girls`), `year` (number), `teams` (`id`, `name`, `classification`), `games` (`date` YYYY-MM-DD, `home`, `away`, `homeGoals`, `awayGoals`, `source`). The source must be an HTTPS URL on kshsaa.org; the site checks the URL format but cannot verify its content. Independently verify results against the source before publication. The template's example match is fictitious and must not be published as a real result.

Data is stored in the current browser's localStorage. Other visitors will not see imported data. For public shared rankings, create a hosted ingestion/publishing pipeline and verify source rights, fetch permissions, and any applicable robots restrictions.

## Model
35% match outcome, 30% opponents' iterative strength, 20% capped goal differential, 15% opponent-adjusted performance. Thirty-five iterative passes, using all statewide matches in the selected gender and season; classification filters are applied after calculating statewide ratings. This is a model, not an official KSHSAA ranking.

## Caveats
This is a complete static frontend with working import, filtering, rankings, profiles, season archive and export; it is not a live data service. Matches are assumed to have one final score, including any extra time. No penalty-shootout result representation is currently implemented.

## Current-season collector (added)
Install Python 3.12, `pip install requests beautifulsoup4`, then run `python scripts/collect.py --gender boys --year 2026`. Results go to `data/boys-2026.json`, with unmatched names/conflicts in `data/boys-2026-review.json`. The website automatically loads published season JSON if present. Girls collection starts with `--gender girls --year 2027` when the spring schedules exist. A GitHub Actions workflow is included, but runs only after you publish the repository to GitHub and enable Actions.

**Important:** The collector has not been live-tested against KSHSAA HTML in this environment (outbound site access blocked). It may require adjustments to selectors, school-name normalization, and neutral-game handling. Review the generated JSON and review report before making rankings public. Check KSHSAA's robots.txt, usage rules, and any required permission before enabling scheduled collection. The workflow currently targets 2026 boys only. Results already archived are preserved, not overwritten by subsequent crawls. A future season needs its own scheduled command. No live public site has been deployed.
