# PostHog Analytics Integration Guide

## Overview

PostHog analytics has been integrated into molt-speak to track:
- **Download rates** (first-run/installation detection)
- **Update rates** (version change detection)
- **Session lengths** (app usage duration)
- **User engagement** (voice interactions, feature usage)
- **Bot detection** (suspicious behavior patterns)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs `posthog>=3.0.0` along with all other dependencies.

### 2. Configure PostHog

Create a `.env` file in the project root with your PostHog credentials:

```bash
cp .env.example .env
```

Edit `.env` and add your PostHog project API key:

```bash
POSTHOG_API_KEY=your_project_api_key_here
POSTHOG_HOST=https://app.posthog.com
POSTHOG_DISABLED=false
```

**Getting Your API Key:**
1. Log in to PostHog (https://app.posthog.com or your self-hosted instance)
2. Go to Project Settings → API Keys
3. Copy your Project API Key
4. Paste it into the `.env` file

### 3. Start Using the App

The analytics will automatically track events when you run the application:

```bash
# Start the unified menu bar app
python unified_menu_bar.py

# Or start individual components
python main.py                    # Coordinator
python open_ears/main.py          # Voice input
python open_mouth/main.py         # Voice output
```

## Tracked Events

### Installation & Updates

| Event | Description | Properties |
|-------|-------------|------------|
| `app_installed` | First time app runs | `install_date`, `app_version`, `platform` |
| `app_updated` | App version changed | `previous_version`, `new_version`, `total_sessions` |

### Sessions

| Event | Description | Properties |
|-------|-------------|------------|
| `session_started` | App session begins | `session_number`, `app_version` |
| `session_ended` | App session ends | `duration_seconds`, `duration_minutes`, `interactions`, `voice_interactions`, `is_suspicious` |

### Voice Loop

| Event | Description | Properties |
|-------|-------------|------------|
| `voice_loop_started` | Voice loop activated | `triggered_by` (user/auto_start) |
| `voice_loop_stopped` | Voice loop deactivated | `triggered_by` |
| `coordinator_started` | Coordinator started | `integration_enabled` |
| `coordinator_stopped` | Coordinator stopped | `reason` (optional) |

### Voice Input (Ears)

| Event | Description | Properties |
|-------|-------------|------------|
| `ears_started` | Voice input started | `model`, `compute_type`, `speech_threshold`, `silence_duration` |
| `ears_stopped` | Voice input stopped | `reason` (normal_shutdown/user_interrupt) |
| `voice_transcription` | Speech transcribed | `transcription_time`, `total_latency`, `text_length`, `word_count`, `model_size` |

### Voice Output (Mouth)

| Event | Description | Properties |
|-------|-------------|------------|
| `mouth_started` | Voice output started | `voice`, `rate`, `use_local_tts`, `control_enabled` |
| `mouth_stopped` | Voice output stopped | `reason` (normal_shutdown/user_interrupt) |
| `voice_synthesis_local` | TTS synthesis (local) | `text_length`, `word_count`, `voice`, `tts_provider` |
| `voice_synthesis_cloud` | TTS synthesis (cloud) | `text_length`, `word_count`, `voice`, `tts_provider` |
| `tts_barge_in` | User interrupted TTS | `tts_provider` |

### Echo Prevention

| Event | Description | Properties |
|-------|-------------|------------|
| `echo_prevention_activated` | Microphone paused | `action` = "pause_microphone" |
| `echo_prevention_deactivated` | Microphone resumed | `action` = "resume_microphone" |

### User Actions

| Event | Description | Properties |
|-------|-------------|------------|
| `menu_bar_started` | Menu bar app launched | - |
| `voice_changed` | User changed TTS voice | `voice_name`, `mouth_was_running` |

## Bot Detection

The analytics system automatically flags suspicious behavior patterns:

### Heuristics

- **Very short sessions** (< 5 seconds)
- **Long sessions with no voice interactions** (> 60s with 0 voice events)
- **Extremely high interaction rate** (> 10 actions/second)

### Suspicious Session Indicators

Sessions flagged as suspicious include:
- `is_suspicious`: `true` in `session_ended` event
- Logged warnings in application logs

### How to Identify Bots in PostHog

1. **Filter by session length:**
   ```
   session_ended.duration_seconds < 5
   ```

2. **Filter by suspicious flag:**
   ```
   session_ended.is_suspicious = true
   ```

3. **Check interaction patterns:**
   ```
   session_ended.interactions > 0 AND session_ended.voice_interactions = 0
   ```

4. **Analyze user retention:**
   - Real users: Multiple sessions over time
   - Bots: Single session or rapid repeated sessions

## Key Metrics to Track

### Download Rate
- **Event:** `app_installed`
- **Unique Users:** Count distinct `user_id` with this event
- **Growth:** Track new installs over time

### Update Rate
- **Event:** `app_updated`
- **Formula:** `app_updated events / total unique users`
- **Retention:** Track which users update vs. abandon

### Session Length
- **Event:** `session_ended`
- **Metric:** `duration_minutes` average
- **Dashboard:**
  - Average session length
  - Median session length
  - Distribution histogram

### Engagement Metrics
- **Voice Interactions per Session:** `voice_interactions / sessions`
- **Features Used:** Track which components are started
- **Voice Preferences:** Most popular TTS voices

### Retention Analysis
- **DAU/WAU/MAU:** Daily/Weekly/Monthly Active Users
- **Cohort Analysis:** Track user retention over time
- **Churn Rate:** Users who stop using the app

## Analytics Architecture

### Component Structure

```
src/services/analytics.py
├── AnalyticsManager          # Main analytics class
│   ├── __init__()            # Initialize PostHog
│   ├── start_session()       # Track session start
│   ├── end_session()         # Track session end + duration
│   ├── track_event()         # Track custom events
│   ├── track_voice_interaction()  # Track voice events
│   └── _detect_suspicious_behavior()  # Bot detection
```

### Data Flow

```
App Startup
    ↓
Initialize Analytics (main.py, ears/main.py, mouth/main.py)
    ↓
Start Session
    ↓
Track Events (user actions, voice interactions)
    ↓
End Session (calculates duration, flags suspicious)
    ↓
Shutdown (flush events to PostHog)
```

### Persistent State

Analytics state is stored in:
```
runtime/analytics_state.json
```

Contains:
- `user_id`: Unique anonymous user identifier (UUID)
- `app_version`: Current application version
- `install_date`: First run timestamp
- `total_sessions`: Lifetime session count
- `total_runtime_seconds`: Lifetime usage time
- `last_session_date`: Most recent session

### Privacy & Anonymity

- **No PII collected:** All users are anonymous UUIDs
- **No transcription content:** Only metadata (length, word count)
- **No TTS content:** Only synthesis metrics
- **Local storage:** User ID persisted locally only

## Disabling Analytics

### Temporary Disable (Environment Variable)

```bash
# In .env file
POSTHOG_DISABLED=true
```

### Permanent Disable (Remove Package)

```bash
pip uninstall posthog
```

The app will gracefully handle missing PostHog dependency and continue working without analytics.

## Troubleshooting

### Analytics Not Working

1. **Check API Key:**
   ```bash
   echo $POSTHOG_API_KEY
   # or
   cat .env | grep POSTHOG_API_KEY
   ```

2. **Check PostHog connection:**
   ```python
   import posthog
   posthog.api_key = "your_key"
   posthog.host = "https://app.posthog.com"
   posthog.capture("test_user", "test_event")
   posthog.shutdown()
   ```

3. **Check logs:**
   ```bash
   # Look for analytics-related warnings
   grep -i "analytics\|posthog" logs/*.log
   ```

### Events Not Appearing in PostHog

- **Delay:** Events can take 1-2 minutes to appear
- **Flush:** Events are flushed on app shutdown
- **Network:** Check internet connection
- **Project:** Verify correct API key for your project

### User ID Not Persisting

- **Permissions:** Check write access to `runtime/` directory
- **File:** Verify `runtime/analytics_state.json` exists
- **Format:** Ensure JSON is valid

## Dashboard Examples

### PostHog Insights to Create

1. **Daily Active Users (DAU)**
   - Event: `session_started`
   - Aggregation: Unique users
   - Interval: Daily

2. **Average Session Length**
   - Event: `session_ended`
   - Property: `duration_minutes`
   - Aggregation: Average

3. **Voice Interaction Rate**
   - Events: `voice_transcription`, `voice_synthesis_*`
   - Formula: `voice_events / sessions`

4. **Installation Funnel**
   - Steps: `app_installed` → `session_started` → `voice_loop_started`

5. **Bot Detection**
   - Event: `session_ended`
   - Filter: `is_suspicious = true`
   - Breakdown: Suspicious reasons

6. **Feature Adoption**
   - Events: `ears_started`, `mouth_started`, `coordinator_started`
   - Chart: Stacked bar showing which components are used

7. **Voice Preferences**
   - Event: `voice_changed`
   - Property: `voice_name`
   - Chart: Top voices by popularity

## Advanced Usage

### Custom Event Tracking

Add custom events in your code:

```python
from src.services.analytics import get_analytics

analytics = get_analytics()
analytics.track_event("custom_event", {
    "property1": "value1",
    "property2": 123
})
```

### Voice Interaction Tracking

```python
analytics.track_voice_interaction("custom_interaction",
    duration=1.5,
    quality="high",
    custom_property="value"
)
```

### Bot Detection Tuning

Edit `src/services/analytics.py` → `_detect_suspicious_behavior()`:

```python
# Adjust thresholds
if session_duration < 5:  # Change minimum session time
if interaction_rate > 10:  # Change max interaction rate
```

## Support

For issues or questions:
- GitHub Issues: https://github.com/jamescodes84/molt-speak/issues
- PostHog Docs: https://posthog.com/docs

---

**Version:** 1.0.0
**Last Updated:** 2026-02-06
**Integration Status:** ✅ Complete
