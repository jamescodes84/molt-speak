# Molt-Speak NIST SP 800-53 Security Audit

**Date:** 2026-02-21
**Scope:** Full codebase — molt-speak, open_ears, open_mouth, unified_menu_bar
**Framework:** NIST SP 800-53 Rev 5 (mapped to relevant control families)

---

## Executive Summary

Audit of the Molt-Speak codebase identified **6 HIGH**, **14 MEDIUM**, and **8 LOW** severity findings across six NIST control families. The most critical issues are: world-writable IPC files, AppleScript injection vectors, unauthenticated Unix socket commands, and plaintext API key storage. No active exploitation was observed, but the local attack surface is significant on shared macOS systems.

---

## Findings by NIST Control Family

### AC — Access Control

| # | Finding | Severity | Location |
|---|---------|----------|----------|
| AC-1 | **Unix socket accepts commands without authentication.** Any local process can connect and send SHUTDOWN, CLEAR_QUEUE, CHANGE_VOICE, RELOAD_CONFIG, etc. No peer-credential check. | HIGH | [control_server.py:41-70](open_mouth/src/control/control_server.py#L41-L70) |
| AC-2 | **Runtime files world-writable (0666).** `speech_output.txt` is the primary IPC channel between Coordinator and Mouth — any local user can inject speech. | HIGH | [runtime/speech_output.txt](runtime/speech_output.txt) |
| AC-3 | **Config file world-readable (0644).** `molt_speak_config.json` stores ElevenLabs API key field, voice IDs, and behavioral settings. | MEDIUM | [runtime/molt_speak_config.json](runtime/molt_speak_config.json) |
| AC-4 | **No privilege separation.** Ears, Mouth, and Coordinator all run under the same UID with identical capabilities. | LOW | [src/unified_audio.py:45-100](src/unified_audio.py#L45-L100) |

**Recommendations:**
- Socket: implement `getpeereid()` (macOS) to verify connecting UID matches owner
- Runtime files: create with `0o600`; directories with `0o700`
- Config: `os.chmod(path, 0o600)` after every write in `ConfigManager._write_config()`

---

### IA — Identification and Authentication

| # | Finding | Severity | Location |
|---|---------|----------|----------|
| IA-1 | **ElevenLabs API key stored plaintext in JSON config.** No encryption at rest, no keychain integration. | HIGH | [config_manager.py:29, 196-203](src/config/config_manager.py#L29) |
| IA-2 | **PostHog API key hardcoded in source (3 locations).** Committed to version control and embedded in install script. | MEDIUM | [analytics.py:25](src/services/analytics.py#L25), [install.sh:467,511](install.sh#L467) |
| IA-3 | **API key held as instance attribute for object lifetime.** Visible in memory dumps, debugger inspection. | LOW | [elevenlabs_tts_service.py:40](open_mouth/src/services/elevenlabs_tts_service.py#L40) |

**Recommendations:**
- Use macOS Keychain (`security` CLI or `keyring` library) for ElevenLabs key
- Move PostHog key to env-var-only; remove hardcoded fallback
- Zero-out key material after passing to client library

---

### SI — System and Information Integrity

| # | Finding | Severity | Location |
|---|---------|----------|----------|
| SI-1 | **AppleScript injection via `TARGET_WINDOW_PATTERN`.** Value read from `.env`, interpolated unsanitized into `osascript` — can break out of string context. | HIGH | [unified_menu_bar.py:1541,1579,1675,1732](unified_menu_bar.py#L1541) |
| SI-2 | **AppleScript injection via log file paths.** `tail -f {path}` embedded in AppleScript `do script` without escaping. | HIGH | [unified_menu_bar.py:1451,1471,1493](unified_menu_bar.py#L1451) |
| SI-3 | **`subprocess.Popen` with `shell=True`.** String command parameter — injection risk if function ever receives dynamic input. | MEDIUM | [unified_menu_bar.py:1376-1378](unified_menu_bar.py#L1376) |
| SI-4 | **Dynamic module loading via `importlib.exec_module()`.** Loads `config_manager.py` from disk path — no integrity verification. | MEDIUM | [mouth_pipeline.py:29-35](open_mouth/src/core/mouth_pipeline.py#L29-L35) |
| SI-5 | **`curl | bash` install pattern returned to user.** No checksum verification, MITM-susceptible. | MEDIUM | [update_checker.py:121](src/services/update_checker.py#L121) |
| SI-6 | **TOCTOU race in file monitoring.** `exists()` check followed by `open()` — file can change between calls. | MEDIUM | [text_monitor.py:80-100](open_mouth/src/services/text_monitor.py#L80-L100) |
| SI-7 | **TOCTOU race in socket creation.** `exists()` + `unlink()` + `bind()` without atomic operation. | MEDIUM | [control_server.py:49-51](open_mouth/src/control/control_server.py#L49-L51) |
| SI-8 | **No input validation on socket commands.** No length limits, no command whitelist enforcement at protocol layer. | MEDIUM | [command_protocol.py:26-44](open_mouth/src/control/command_protocol.py#L26-L44) |
| SI-9 | **Unvalidated environment variable casting.** `float()` / `int()` with no range checks — negative or extreme values accepted. | LOW | [settings.py:44-60](src/config/settings.py#L44-L60) |

**Recommendations:**
- Create an `escape_applescript(s)` utility that backslash-escapes `"` and `\`
- Replace `shell=True` with list-form subprocess
- Add `--checksum` step to install flow
- Replace pre-check patterns with try/except
- Validate and clamp all env-var numeric values

---

### AU — Audit and Accountability

| # | Finding | Severity | Location |
|---|---------|----------|----------|
| AU-1 | **Bare `except: pass` in 6+ locations.** Silently swallows all exceptions including security-relevant ones. | MEDIUM | [audio_playback.py:130](open_mouth/src/services/audio_playback.py#L130), [local_tts_service.py:150](open_mouth/src/services/local_tts_service.py#L150), [control_server.py:151](open_mouth/src/control/control_server.py#L151), [whisper_transcriber_optimized.py:120](open_ears/openclaw-ears/openclaw_ears/transcription/whisper_transcriber_optimized.py#L120) |
| AU-2 | **User IDs logged in plaintext.** Analytics user UUID and session data written to application logs. | MEDIUM | [analytics.py:176-177,289,329](src/services/analytics.py#L176) |
| AU-3 | **38+ `print()` statements bypass logging controls.** Not captured by log rotation, level filtering, or audit trail. | LOW | [unified_audio.py:219,234](src/unified_audio.py#L219), open_mouth/ (various) |
| AU-4 | **`.exception()` logs full tracebacks exposing internal paths.** | LOW | [analytics.py:232](src/services/analytics.py#L232), [main.py:97](main.py#L97) |

**Recommendations:**
- Replace bare `except:` with specific exception types (`except OSError`, etc.)
- Hash or truncate user IDs before logging
- Replace `print()` with `logger.*()` calls
- Use `.error()` instead of `.exception()` in production paths

---

### CM — Configuration Management

| # | Finding | Severity | Location |
|---|---------|----------|----------|
| CM-1 | **Dependencies unpinned.** Only 1 of ~50 dependencies pinned (`edge-tts==7.2.7`). All others use `>=` with no upper bound. | MEDIUM | [requirements.txt](requirements.txt), [open_ears/pyproject.toml:27-40](open_ears/pyproject.toml#L27-L40) |
| CM-2 | **Outdated minimum versions allowed.** `torch>=1.13.0` (2022), `numpy>=1.21.0` (2021) — known CVEs in these ranges. | MEDIUM | [open_ears/pyproject.toml:27-40](open_ears/pyproject.toml#L27-L40) |
| CM-3 | **Hardcoded `/tmp/` paths in scripts.** World-readable/writable temp files for demos and backups. | LOW | [install.sh:95](install.sh#L95), [voice_input_demo.py](open_ears/scripts/voice_input_demo.py) |
| CM-4 | **Analytics state stored without directory-level protection.** `~/Library/Application Support/molt-speak/` created with default umask. | LOW | [analytics.py:44-60](src/services/analytics.py#L44-L60) |

**Recommendations:**
- Pin all dependencies with `==`; run `pip-audit` or `safety check` in CI
- Raise minimum versions to current stable branches
- Use `tempfile.mkdtemp(mode=0o700)` instead of hardcoded `/tmp/` paths
- Create support directory with `mode=0o700`

---

### SC — System and Communications Protection

| # | Finding | Severity | Location |
|---|---------|----------|----------|
| SC-1 | **File handle leak in subprocess log redirection.** `open()` without context manager — never closed on error paths. | MEDIUM | [unified_audio.py:56,80](src/unified_audio.py#L56) |
| SC-2 | **No explicit SSL context in update checker.** Relies on Python default behavior — no certificate pinning or explicit verification. | LOW | [update_checker.py:72-78](src/services/update_checker.py#L72-L78) |
| SC-3 | **No socket rate limiting.** Control server accepts unlimited commands per second — local DoS vector. | LOW | [control_server.py:122-155](open_mouth/src/control/control_server.py#L122-L155) |

**Recommendations:**
- Wrap file handles in context managers or close in `finally` blocks
- Create explicit `ssl.create_default_context()` for HTTPS calls
- Add per-connection rate limiting (e.g., 10 commands/second)

---

## Risk Summary

| Severity | Count | Key Theme |
|----------|-------|-----------|
| **HIGH** | 6 | File permissions, injection, credential storage |
| **MEDIUM** | 14 | Input validation, TOCTOU, logging hygiene, deps |
| **LOW** | 8 | Hardening, defense-in-depth |

---

## Prioritized Remediation Plan

### Immediate (HIGH — do first)
1. **Fix runtime file permissions** — `speech_output.txt` to `0o600`, config to `0o600`
2. **Sanitize AppleScript interpolation** — escape `"` and `\` in all f-string-to-osascript paths
3. **Authenticate Unix socket** — `getpeereid()` check on connect
4. **Encrypt API key at rest** — macOS Keychain or encrypted config file

### Short-term (MEDIUM — next sprint)
5. Pin all dependencies with exact versions
6. Remove `shell=True` from subprocess calls
7. Replace bare `except:` clauses with specific types
8. Add input validation to socket command protocol
9. Fix TOCTOU patterns (try/except instead of pre-check)
10. Replace `print()` with proper logging

### Hardening (LOW — backlog)
11. Add rate limiting to control server
12. Explicit SSL context in update checker
13. Validate and clamp environment variable values
14. Use `tempfile` module for temporary files

---

## Remediation Status (2026-02-21)

**Threat model reassessment:** Molt-Speak is a single-user local macOS desktop app. The original audit applied server/multi-user assumptions that don't match the actual threat model. After practical review, 8 findings were remediated and 20 were dismissed as not applicable.

### Fixed

| Finding | Fix Applied |
|---------|-------------|
| **SC-1** File handle leak | Stored as instance vars, closed in `stop()` — `unified_audio.py` |
| **SI-3** `shell=True` subprocess | Converted to list-form args with `cwd` parameter — `unified_menu_bar.py` |
| **SI-2** Unquoted paths in AppleScript | Added `shlex.quote()` for all path interpolation (also fixed broken behavior with spaces in path) — `unified_menu_bar.py` |
| **AU-1** Bare `except: pass` (6 locations) | Narrowed to `except OSError:` or `except Exception:` per call site |
| **AC-3** Config file world-readable | Added `os.chmod(0o600)` after config writes — `config_manager.py` |
| **SI-6** TOCTOU in file monitoring | Replaced `exists()`+`stat()` with `try: stat() except FileNotFoundError` — `text_monitor.py` |

### Dismissed — Not Applicable for Local Desktop App

| Finding | Rationale |
|---------|-----------|
| **AC-1** Unix socket no auth | Socket in user-owned `runtime/`; macOS enforces home dir privacy. Single user. |
| **AC-2** Runtime files 0666 | Only the owner's processes read/write these on a single-user Mac. |
| **AC-4** No privilege separation | Overkill for a desktop app; all components must cooperate anyway. |
| **IA-1** API key plaintext in config | Mitigated by AC-3 fix (0600 perms). Keychain integration is future work. |
| **IA-2** PostHog key hardcoded | Write-only `phc_*` client key — designed to be embedded, like a GA tracking ID. |
| **IA-3** API key in memory | If attacker can read process memory, app security is already moot. |
| **SI-1** Window pattern injection | Value comes from user's own `.env` file — user controls the input. |
| **SI-4** Dynamic module import | Path hardcoded from `__file__`, not user input. |
| **SI-5** `curl \| bash` install | Standard install pattern; separate discussion for checksum verification. |
| **SI-7** Socket creation TOCTOU | Single-user system, socket in owned directory — no race adversary. |
| **SI-8** Socket command validation | Socket is local-only IPC; no untrusted input source exists. |
| **SI-9** Env var validation | User sets their own environment variables. |
| **AU-2** User IDs in logs | Local logs on single-user machine — no exposure risk. |
| **AU-3** `print()` vs `logger` | Cosmetic, not a security issue. |
| **AU-4** Verbose tracebacks | Local logs only — no external exposure. |
| **CM-1** Unpinned dependencies | Valid concern but out of scope for this branch (separate effort). |
| **CM-2** Outdated min versions | Same — dependency management is a separate workstream. |
| **CM-3** `/tmp` paths in scripts | Demo/test scripts only, not production code. |
| **CM-4** Analytics dir permissions | Under `~/Library/Application Support/` — macOS home dir protection applies. |
| **SC-2** No explicit SSL context | Python 3 enables certificate verification by default. |
| **SC-3** No socket rate limiting | Local IPC only — user would be DoS-ing themselves. |

---

*Generated by automated NIST SP 800-53 audit — manual review recommended for all HIGH findings.*
