# Automation (launchd + cron)

## macOS — launchd

`~/Library/LaunchAgents/local.secondbrain.maintain.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>local.secondbrain.maintain</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/env</string>
    <string>bash</string>
    <string>-lc</string>
    <string>SECOND_BRAIN_HOME=$HOME/second-brain /usr/local/bin/sb maintain --json >> $HOME/second-brain/.sb/maintain.log 2>&amp;1</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>3</integer><key>Minute</key><integer>30</integer></dict>
  <key>RunAtLoad</key><false/>
</dict>
</plist>
```

Load with `launchctl load ~/Library/LaunchAgents/local.secondbrain.maintain.plist`.

## Linux — cron

```
30 3 * * * SECOND_BRAIN_HOME=$HOME/second-brain /usr/local/bin/sb maintain --json >> $HOME/second-brain/.sb/maintain.log 2>&1
```

## Watch daemon (systemd unit)

```ini
# ~/.config/systemd/user/sb-watch.service
[Unit]
Description=Second Brain inbox watcher

[Service]
Environment=SECOND_BRAIN_HOME=%h/second-brain
ExecStart=/usr/local/bin/sb watch
Restart=on-failure

[Install]
WantedBy=default.target
```

Enable with `systemctl --user enable --now sb-watch.service`.
