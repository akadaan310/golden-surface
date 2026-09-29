#!/bin/bash
cd /home/azureuser/golden-surface || exit 1
PROMPT="Working directory is /home/azureuser/golden-surface. Read SPEC.md and BUILDLOG.md in it, then execute the spec exactly as written."
claude --dangerously-skip-permissions -p "$PROMPT $(cat SPEC.md)" > build-run-1.log 2>&1
