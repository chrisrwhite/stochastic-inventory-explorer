# Publish checklist

Manual steps to flip this repo from private to a public, portfolio-grade
GitHub project. Everything below is intentionally kept out of code so you can
tick items off explicitly before making the repo public.

## 1. GitHub repo metadata (set on the repo page, not in files)

**Description** (paste into the "About" gear on the repo page):

> Educational stochastic-optimization demo: Monte Carlo inventory policy
> explorer with real POS data (Walmart M5, Favorita, UCI Online Retail).

**Topics** (comma-separated in the topics field):

- `stochastic-optimization`
- `operations-research`
- `monte-carlo`
- `inventory-management`
- `simulation`
- `fastapi`
- `react`
- `data-science`
- `portfolio`

**Website field:** your deployed URL (once you have one).

**Pin the repo** on your GitHub profile.

## 2. Update the badges

The README uses this repo slug:

```
github.com/chrisrwhite/stochastic-inventory-explorer
```

If your GitHub username or repo name is different, edit the CI badge URL at
the top of [README.md](../README.md).

## 3. Record and commit a demo GIF

The README has a commented-out `docs/hero.gif` reference. Record 10-15 seconds
of the app in use (pick scenario → set target → optimize → cost-vs-reliability
frontier), save it to `docs/hero.gif`, and uncomment the reference in the
README. See [docs/hero-placeholder.md](../docs/hero-placeholder.md) for
suggested captures.

## 4. Fill in the live demo URL

Once deployed via Cloud Run + Cloudflare:

- Replace "Live demo coming soon" in [README.md](../README.md) with the URL.
- Update the `href` in [docs/portfolio-entry.md](../docs/portfolio-entry.md).
- Set the "Website" field on the GitHub repo.

## 5. Confirm CI is green

Before flipping visibility, push the current branch and confirm the CI
workflow ([.github/workflows/ci.yml](workflows/ci.yml)) is green on `main`. A
red badge on a portfolio repo is worse than no badge.

## 6. Scan history for accidental secrets

```bash
git log --all -p | rg -i 'KGAT_[A-Za-z0-9]|ghp_[A-Za-z0-9]{20,}|sk-live-|GOCSPX-|AKIA[0-9A-Z]{16}|BEGIN (RSA )?PRIVATE KEY'
```

If anything real leaks, decide whether to rewrite history (`git filter-repo`)
or rotate the key and accept the leaked value.

## 6b. Scan for infrastructure identifiers

Not secrets, but awkward to retract once public — and easy to paste in while
debugging a deploy:

```bash
rg -i 'terraform\.tfstate|dash\.cloudflare\.com/[0-9a-f]{32}|[a-z-]+-[0-9]{6}\.iam|projects/[0-9]{6,}' \
  --glob '!.git' --glob '!infra/.terraform/'
```

The README's ops table is deliberately ID-free and the GCP project ID lives
only in `infra/terraform.tfvars` and Terraform state (both gitignored). Confirm
it stayed that way. Also check `infra/terraform.tfstate*` is not tracked:

```bash
git ls-files infra/ | rg -v '\.tf$|\.md$|\.example$|\.lock\.hcl$'   # expect no output
```

## 7. Verify the .gitignore is doing its job

```bash
git status --ignored | rg -i 'venv|node_modules|_raw|\.env$'
```

Confirm `.venv/`, `node_modules/`, `backend/data/scenarios/_raw/`, and any
`.env` file are all listed as ignored.

## 8. Flip visibility

Settings → General → Danger Zone → Change visibility → Make public.

## 9. Optional polish after publishing

- Add a `docs/ARCHITECTURE.md` with the mermaid MC-loop diagram.
- Add a `notebooks/README.md` mirroring the Makefile `notebook` target.
- Wire up a `.pre-commit-config.yaml` with `ruff` + `ruff format` + `eslint`.
