## Setup Gmail and Calendar integration

The `agentor setup-google` command guides you through:

1. **Creating Google Cloud Project** (if needed)
1. **Enabling APIs** (Gmail, Calendar)
1. **OAuth credentials** (desktop app)
1. **Browser authentication** (automatic)
1. **Credential storage** (secure, local)

**1. First run:**

```bash
agentor setup-google
# ✅ Opens browser for one-time authentication
# ✅ Saves credentials locally
# ✅ Ready to use!
```

**2. Already set up:**

```bash
agentor setup-google
# ✅ Google credentials already exist
# Use --force to re-authenticate
```
