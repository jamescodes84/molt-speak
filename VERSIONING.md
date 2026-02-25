# Molt-Speak Versioning Guide

## Overview

Molt-Speak uses **Semantic Versioning** (SemVer) to track releases and enable automatic update notifications.

## Version Format

```
MAJOR.MINOR.PATCH
  │     │     │
  │     │     └─── Bug fixes, minor tweaks (1.0.1, 1.0.2)
  │     └───────── New features, backwards-compatible (1.1.0, 1.2.0)
  └─────────────── Breaking changes, major overhauls (2.0.0, 3.0.0)
```

### Examples

- **1.0.0** → Initial release
- **1.0.1** → Bug fix (transcription accuracy)
- **1.1.0** → New feature (ElevenLabs support added)
- **2.0.0** → Breaking change (new configuration format)

---

## Where Versions Are Stored

### Single Source of Truth: `VERSION` File

```bash
# File: VERSION
1.0.0
```

**This file is used by:**
- ✅ Analytics system (`app_version` in events)
- ✅ Update checker (compares with GitHub releases)
- ✅ Menu bar app (displays current version)

**Never hardcode versions elsewhere!** Always read from `VERSION` file.

---

## Release Workflow

### 1. Planning a Release

Before starting:
- Decide version number based on changes
- Review changelog
- Test all features

### 2. Version Bump Process

#### Step 1: Update VERSION File

```bash
# Example: Going from 1.0.0 → 1.1.0
echo "1.1.0" > VERSION
```

#### Step 2: Update CHANGELOG.md (Recommended)

Create a changelog if you don't have one:

```bash
cat > CHANGELOG.md << 'EOF'
# Changelog

All notable changes to Molt-Speak will be documented here.

## [1.1.0] - 2025-01-15

### Added
- PostHog analytics integration
- Auto-update checker
- Bot detection in analytics

### Changed
- Improved voice synthesis performance

### Fixed
- Echo prevention timing issues

## [1.0.0] - 2025-01-01

### Added
- Initial release
- Voice input (STT) with Whisper
- Voice output (TTS) with Edge-TTS
- Echo prevention system
EOF
```

#### Step 3: Commit Changes

```bash
git add VERSION CHANGELOG.md
git commit -m "Bump version to 1.1.0"
git push origin main
```

#### Step 4: Create Git Tag

```bash
# Create annotated tag (recommended)
git tag -a v1.1.0 -m "Release version 1.1.0"

# Push tag to GitHub
git push origin v1.1.0
```

#### Step 5: Create GitHub Release

**Option A: Via GitHub UI (Recommended)**
1. Go to https://github.com/jamescodes84/molt-speak/releases/new
2. Choose tag: `v1.1.0`
3. Release title: `Version 1.1.0`
4. Description: Copy from CHANGELOG.md
5. Click "Publish release"

**Option B: Via GitHub CLI**
```bash
gh release create v1.1.0 \
  --title "Version 1.1.0" \
  --notes "$(cat CHANGELOG.md | sed -n '/## \[1.1.0\]/,/## \[1.0.0\]/p' | head -n -1)"
```

### 3. Users Get Auto-Notified! 🎉

- Update checker runs when users open app
- Compares their `VERSION` (e.g., 1.0.0) with GitHub latest (1.1.0)
- Shows update prompt if newer version available

---

## Version Comparison Logic

The update checker uses semantic versioning comparison:

```python
from packaging import version

current = version.parse("1.0.0")
latest = version.parse("1.1.0")

if latest > current:
    # Show update prompt
```

### Valid Comparisons

```python
"1.0.1" > "1.0.0"   # ✅ Patch bump
"1.1.0" > "1.0.9"   # ✅ Minor bump
"2.0.0" > "1.9.9"   # ✅ Major bump
"1.0.0" = "1.0.0"   # ✅ Same version
```

### Invalid Formats (Avoid!)

```
❌ "v1.0.0"      # Don't include 'v' in VERSION file
❌ "1.0"         # Must have 3 parts (MAJOR.MINOR.PATCH)
❌ "1.0.0-beta"  # No pre-release tags (yet)
```

**Note:** Git tags should include `v` prefix (`v1.0.0`), but VERSION file should not.

---

## Release Checklist

Use this checklist for every release:

### Pre-Release
- [ ] All tests passing
- [ ] Features tested manually
- [ ] Analytics events verified in PostHog
- [ ] Update checker tested (temporarily set old version)
- [ ] Documentation updated (README, guides)

### Release
- [ ] Update VERSION file (`echo "X.Y.Z" > VERSION`)
- [ ] Update CHANGELOG.md with release notes
- [ ] Commit changes (`git commit -m "Bump version to X.Y.Z"`)
- [ ] Create git tag (`git tag -a vX.Y.Z -m "Release X.Y.Z"`)
- [ ] Push to GitHub (`git push && git push --tags`)
- [ ] Create GitHub Release with notes

### Post-Release
- [ ] Verify GitHub Release appears at: https://github.com/jamescodes84/molt-speak/releases
- [ ] Test update checker detects new version
- [ ] Monitor PostHog for `update_available` events
- [ ] Check for user-reported issues

---

## Version History Template

Track your releases in a table:

| Version | Date       | Type    | Highlights                        |
|---------|------------|---------|-----------------------------------|
| 1.1.0   | 2025-01-15 | Feature | PostHog analytics, update checker |
| 1.0.1   | 2025-01-08 | Patch   | Fix echo prevention timing        |
| 1.0.0   | 2025-01-01 | Major   | Initial release                   |

---

## Hotfix Process

For urgent bug fixes between releases:

```bash
# Current: 1.1.0
# Bug discovered!

# 1. Fix the bug
git checkout -b hotfix/critical-bug
# ... make fixes ...

# 2. Bump patch version
echo "1.1.1" > VERSION

# 3. Commit and merge
git commit -am "Fix critical bug"
git checkout main
git merge hotfix/critical-bug

# 4. Tag and release
git tag -a v1.1.1 -m "Hotfix: Critical bug"
git push && git push --tags

# 5. Create GitHub Release
gh release create v1.1.1 --title "Version 1.1.1 (Hotfix)" --notes "Fixed critical bug affecting..."
```

---

## Pre-Release Versions (Beta/Alpha)

For testing with early adopters:

### Beta Version Format
```
1.2.0-beta.1
1.2.0-beta.2
1.2.0         # Final release
```

### How to Release Beta

```bash
# 1. Update VERSION with beta suffix
echo "1.2.0-beta.1" > VERSION

# 2. Tag as pre-release
git tag -a v1.2.0-beta.1 -m "Beta release 1.2.0-beta.1"
git push origin v1.2.0-beta.1

# 3. Create GitHub Release (mark as pre-release)
# Check "This is a pre-release" box
```

**Important:** Update checker will **not** prompt users to upgrade to beta versions by default (semantic versioning considers "1.2.0-beta.1" < "1.1.0").

---

## Troubleshooting

### Update Checker Not Finding Latest Release

**Problem:** Users not seeing update notification

**Check:**
1. GitHub Release exists at: https://github.com/jamescodes84/molt-speak/releases
2. Release is published (not draft)
3. Tag format is correct: `v1.1.0` (with `v` prefix)
4. VERSION file is correct: `1.1.0` (no `v` prefix)

**Debug:**
```bash
# Check GitHub API returns latest release
curl https://api.github.com/repos/jamescodes84/molt-speak/releases/latest | jq '.tag_name'

# Should return: "v1.1.0"
```

### Version Mismatch in Analytics

**Problem:** PostHog shows wrong version

**Solution:**
```bash
# 1. Check VERSION file
cat VERSION

# 2. Verify analytics reads it
python3 -c "
from src.services.analytics import AnalyticsManager
a = AnalyticsManager()
print(f'Analytics version: {a.app_version}')
"

# 3. Should match VERSION file
```

### Users Stuck on Old Version

**Problem:** Users see update but don't update

**Analytics Query (PostHog):**
```sql
SELECT
  properties.app_version,
  COUNT(DISTINCT properties.user_id) as users,
  MAX(timestamp) as last_seen
FROM events
WHERE event = 'session_started'
GROUP BY properties.app_version
ORDER BY last_seen DESC
```

**Follow-up Actions:**
- Send notification about critical update
- Check `update_dismissed` rate (users clicking "Later")
- Consider making update process easier

---

## Best Practices

### 1. Version Consistently
- ✅ **Do:** Increment version for every release
- ❌ **Don't:** Skip versions (1.0.0 → 1.2.0)
- ❌ **Don't:** Release without updating VERSION

### 2. Tag Everything
- ✅ **Do:** Create git tag for every release
- ✅ **Do:** Use annotated tags (`-a`)
- ❌ **Don't:** Create releases without tags

### 3. Write Clear Release Notes
- ✅ **Do:** List what changed for users
- ✅ **Do:** Categorize: Added/Changed/Fixed/Removed
- ❌ **Don't:** Use technical jargon
- ❌ **Don't:** Skip release notes

### 4. Test Before Release
- ✅ **Do:** Test update checker with old version
- ✅ **Do:** Verify analytics tracking
- ❌ **Don't:** Release without testing

### 5. Communicate Breaking Changes
- ✅ **Do:** Bump major version for breaking changes
- ✅ **Do:** Document migration steps
- ✅ **Do:** Give users advance notice

---

## Quick Reference

### Bump Patch (Bug Fixes)
```bash
echo "1.0.1" > VERSION
git commit -am "Bump to 1.0.1"
git tag -a v1.0.1 -m "v1.0.1"
git push && git push --tags
```

### Bump Minor (New Features)
```bash
echo "1.1.0" > VERSION
git commit -am "Bump to 1.1.0"
git tag -a v1.1.0 -m "v1.1.0"
git push && git push --tags
```

### Bump Major (Breaking Changes)
```bash
echo "2.0.0" > VERSION
git commit -am "Bump to 2.0.0"
git tag -a v2.0.0 -m "v2.0.0"
git push && git push --tags
```

### Check Current Version
```bash
cat VERSION
```

### List All Releases
```bash
git tag -l "v*"
# or
gh release list
```

---

## Integration with CI/CD (Future)

When you're ready to automate:

```yaml
# .github/workflows/release.yml
name: Release
on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          generate_release_notes: true
```

---

## Summary

- **Version file:** `VERSION` (single source of truth)
- **Format:** `MAJOR.MINOR.PATCH` (semantic versioning)
- **Git tags:** `vMAJOR.MINOR.PATCH` (with `v` prefix)
- **Releases:** Create on GitHub for update checker
- **Analytics:** Automatically tracks version in all events

**Next release:** Update VERSION → Tag → GitHub Release → Users notified! 🚀

---

**Last Updated:** 2026-02-06
**Current Version:** 1.0.0
