# PostHog Analytics Setup - Quick Reference

## 🎯 Status: READY FOR DEPLOYMENT ✅

Your PostHog analytics is **fully configured** and tested. Analytics will automatically work when users install your app.

---

## 📋 Quick Summary

### What's Working
- ✅ PostHog API key configured in install.sh
- ✅ Analytics tracking in all components (coordinator, ears, mouth, menu bar)
- ✅ Test event successfully sent to PostHog
- ✅ Privacy-conscious (no PII, anonymous UUIDs only)
- ✅ Opt-out mechanism available
- ✅ Graceful degradation if PostHog unavailable

### Configuration
```bash
API Key: ${POSTHOG_API_KEY}  # Set in .env (auto-created by install.sh)
Host: https://app.posthog.com
Auto-enabled: Yes (via install.sh)
```

---

## 🚀 Next Steps

### 1. Verify in PostHog Dashboard (5 min)
Visit https://app.posthog.com and look for:
- Event: `deployment_test`
- User ID: `<ANONYMOUS_UUID>` (check your local analytics_state.json)

### 2. Add Privacy Disclosure (10 min)
Add content from `docs/deployment/PRIVACY_SECTION.md` to your README.md

### 3. Create PostHog Dashboards (30 min)
- Overview: DAU, installs, session length
- Engagement: Voice interactions, feature usage
- Quality: Errors, suspicious sessions

### 4. Beta Test (1 week)
Share install script with 5-10 users and monitor PostHog

---

## 📊 Events Being Tracked

| Event | Description |
|-------|-------------|
| `app_installed` | First-time installation |
| `app_updated` | Version upgrade |
| `session_started` / `session_ended` | Usage sessions with duration |
| `voice_transcription` | Speech-to-text with latency |
| `voice_synthesis_*` | TTS events |
| `coordinator_started` / `stopped` | Integration coordinator |
| `ears_started` / `mouth_started` | Component launches |
| `voice_changed` | User changed TTS voice |

**Privacy:** No content is tracked—only metadata like duration, word count, latency.

---

## 🔧 User Opt-Out

Users can disable analytics by editing `.env`:
```bash
POSTHOG_DISABLED=true
```

App functionality is unchanged when analytics are disabled.

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| [ANALYTICS_GUIDE.md](ANALYTICS_GUIDE.md) | Complete event reference & PostHog setup |
| [docs/deployment/posthog_deployment_summary.md](docs/deployment/posthog_deployment_summary.md) | Detailed deployment guide |
| [docs/deployment/deployment_checklist.md](docs/deployment/deployment_checklist.md) | Step-by-step checklist |
| [docs/deployment/PRIVACY_SECTION.md](docs/deployment/PRIVACY_SECTION.md) | Privacy text for README |

---

## 🆘 Troubleshooting

**Events not appearing?**
1. Wait 1-2 minutes for PostHog processing
2. Check internet connectivity
3. Verify API key at https://app.posthog.com/settings/project
4. Check PostHog status: https://status.posthog.com

**Need to change API key?**
Edit `install.sh` line 388 and `.env.example` line 30

---

## ✅ Final Checklist

- [ ] Verify test event in PostHog dashboard
- [ ] Add privacy section to README
- [ ] Set up PostHog dashboards
- [ ] Test install.sh on clean machine
- [ ] Beta test with real users

**You're ready to deploy!** 🎉

---

For detailed guidance, see: `docs/deployment/posthog_deployment_summary.md`
