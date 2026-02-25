# Privacy & Analytics Section (Add to README.md)

## Privacy & Analytics

### What We Track

Molt-Speak uses PostHog analytics to understand usage patterns and improve the product. We track:

- **Installation & Updates** - When you install or update the app
- **Session Duration** - How long you use the app
- **Feature Usage** - Which features you use (voice input, output, etc.)
- **Performance Metrics** - Transcription times, synthesis times
- **Anonymous User ID** - A randomly generated UUID (not linked to your identity)

### What We DON'T Track

- ❌ No transcribed speech content
- ❌ No text-to-speech content
- ❌ No personal information (name, email, etc.)
- ❌ No file contents or system information beyond platform type
- ❌ No IP addresses (PostHog anonymizes these)

### Opting Out

To disable analytics entirely, edit your `.env` file:

```bash
# Open the file
nano ~/openclaw-workspace/molt-speak/app/.env

# Change this line:
POSTHOG_DISABLED=true

# Save and restart Molt-Speak
moltspeak quit
moltspeak start
```

The app will function identically with analytics disabled.

### Data Retention

Analytics data is stored in PostHog cloud (https://app.posthog.com) and retained according to PostHog's data retention policies. You can request data deletion by opening an issue on our GitHub repository.

### Open Source

All analytics code is open source and auditable in this repository. See [src/services/analytics.py](src/services/analytics.py) for implementation details.
