#!/bin/bash
# Wrapper script to run settings migration without old environment variables

cd "$(dirname "$0")"

# Unset old environment variables
unset CONFIDENCE_THRESHOLD_LOW
unset CONFIDENCE_THRESHOLD_HIGH
unset USE_CLAUDE_FALLBACK_THRESHOLD
unset ENABLE_CLAUDE_FALLBACK

# Run migration
python3 -m app.migrations.migrate_settings "$@"
