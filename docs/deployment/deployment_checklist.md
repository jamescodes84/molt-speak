# Molt-Speak PostHog Deployment Checklist

## Pre-Deployment

- [ ] **Verify PostHog API Key**
  - Log in to https://app.posthog.com
  - Confirm project exists for your `POSTHOG_API_KEY` (set in `.env`)
  - Check Project Settings → API Keys → Verify key is active

- [ ] **Test Event Ingestion**
  - Run local test: `python3 -c "from src.services.analytics import get_analytics; a = get_analytics(); a.track_event('test'); a.shutdown()"`
  - Wait 1-2 minutes
  - Check PostHog dashboard for test event
  - Verify user_id, app_version, and properties appear correctly

- [ ] **Test Installation Flow**
  - Run install.sh on a clean test machine
  - Verify .env file is created automatically
  - Verify POSTHOG_API_KEY is present in .env
  - Launch molt-speak and check for analytics events

## Beta Testing (5-10 users)

- [ ] **Share install script with beta testers**
  ```bash
  curl -fsSL https://raw.githubusercontent.com/jamescodes84/molt-speak/main/install.sh | bash
  ```

- [ ] **Monitor PostHog Dashboard**
  - Track "app_installed" events (new installs)
  - Track "session_started" events (active usage)
  - Monitor session durations and engagement
  - Check for error events or suspicious behavior flags

- [ ] **Verify Bot Detection**
  - Check for sessions flagged with `is_suspicious: true`
  - Review suspicious sessions (< 5 seconds, no voice interactions)
  - Adjust heuristics in analytics.py if needed

- [ ] **Test Opt-Out Flow**
  - Have 1 beta tester set POSTHOG_DISABLED=true
  - Verify app works normally
  - Confirm no events are sent for that user

## Post-Deployment Monitoring

- [ ] **Set Up PostHog Dashboards**
  - Daily Active Users (DAU)
  - Average Session Length
  - Voice Interaction Rate
  - Installation Funnel
  - Update Adoption Rate

- [ ] **Set Up Alerts** (Optional)
  - Alert if DAU drops significantly
  - Alert if error events spike
  - Alert if average session length drops to < 30 seconds (may indicate bugs)

- [ ] **Weekly Review (First Month)**
  - Review new user retention (Day 1, Day 7, Day 30)
  - Identify most/least used features
  - Look for patterns in churned users
  - Review bot detection accuracy

## Common Issues & Solutions

### Issue: Events not appearing in PostHog
**Solution:**
1. Check internet connectivity
2. Verify API key hasn't been rotated
3. Check PostHog status: https://status.posthog.com
4. Look for errors in logs: `moltspeak logs`

### Issue: Too many bot-flagged sessions
**Solution:**
1. Review suspicious session logs in PostHog
2. Adjust thresholds in src/services/analytics.py:
   - `session_duration < 5` (line 256)
   - `interaction_rate > 10` (line 267)
3. Push update with new thresholds

### Issue: Users concerned about privacy
**Solution:**
1. Point to privacy section in README
2. Explain no PII is collected
3. Provide opt-out instructions
4. Offer to delete their data if requested

## Analytics Insights to Track

### Download Rate
- **Metric:** Count of `app_installed` events
- **Goal:** Understand growth trajectory
- **PostHog Query:**
  ```text
  Event: app_installed
  Aggregation: Total Count
  Interval: Daily
  ```

### Update Rate
- **Metric:** `app_updated` events / Total Unique Users
- **Goal:** Understand engagement and update adoption
- **PostHog Query:**
  ```
  Event: app_updated
  Aggregation: Unique Users
  Compare to: Total Unique Users
  ```

### Session Length
- **Metric:** Average `session_ended.duration_minutes`
- **Goal:** Understand engagement depth
- **Target:** > 5 minutes average
- **PostHog Query:**
  ```
  Event: session_ended
  Property: duration_minutes
  Aggregation: Average
  ```

### Voice Interaction Rate
- **Metric:** `voice_transcription` + `voice_synthesis_*` events / sessions
- **Goal:** Understand actual voice usage vs. passive use
- **Target:** > 3 voice interactions per session
- **PostHog Formula:**
  ```text
  (voice_transcription + voice_synthesis_local + voice_synthesis_cloud) / session_started
  ```

### Feature Adoption
- **Metrics:** 
  - % users who start ears: `ears_started` / total users
  - % users who start mouth: `mouth_started` / total users
  - % users who change voices: `voice_changed` / total users
- **Goal:** Understand which features are valued

## Success Criteria

✅ **Week 1:**
- [ ] > 10 successful installations
- [ ] > 5 daily active users
- [ ] Average session length > 3 minutes
- [ ] < 20% sessions flagged as suspicious

✅ **Week 4:**
- [ ] > 50 total installations
- [ ] > 20 daily active users
- [ ] 7-day retention > 30%
- [ ] Average session length > 5 minutes
- [ ] > 80% of users have voice interactions

✅ **Month 3:**
- [ ] > 200 total installations
- [ ] > 50 daily active users
- [ ] 30-day retention > 20%
- [ ] Clear feature usage patterns identified
- [ ] At least 1 update shipped based on analytics insights

---

## PostHog Dashboard Templates

### 1. Overview Dashboard
- Total Users (Unique `user_id`)
- DAU/WAU/MAU trends
- New Installs (Daily `app_installed`)
- Active Sessions (Daily `session_started`)
- Average Session Length

### 2. Engagement Dashboard
- Voice Interactions per Session
- Feature Usage Breakdown (ears, mouth, coordinator)
- Voice Preferences (most popular voices)
- Barge-in Rate (user interruptions)

### 3. Quality Dashboard
- Suspicious Sessions (Bot Detection)
- Error Events
- Average Transcription Latency
- Average Synthesis Time

### 4. Retention Dashboard
- Cohort Analysis (by install week)
- User Lifecycle (New → Active → Churned)
- Update Adoption Rate
- Time to First Voice Interaction

---

**Reference:** [ANALYTICS_GUIDE.md](../ANALYTICS_GUIDE.md) for detailed event documentation
