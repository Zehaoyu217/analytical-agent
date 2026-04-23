# launchd schedules for second-brain

Daily digest at 03:00 local.

`com.jay.second-brain.digest.plist` is shipped as a template. Replace:

- `__REPO_ROOT__`
- `__SECOND_BRAIN_HOME__`

before loading it. The job should run `.venv/bin/sb maintain --digest` from the
component repo working directory and write logs under the KB data home.

## Load (bootstrap)

    launchctl bootstrap gui/$UID ops/launchd/com.jay.second-brain.digest.plist

## Unload (bootout)

    launchctl bootout gui/$UID/com.jay.second-brain.digest

## Check status

    launchctl print gui/$UID/com.jay.second-brain.digest
