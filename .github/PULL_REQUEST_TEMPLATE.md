## What does this change?

One or two sentences, plus the issue it closes if there is one (`Closes #123`).

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Docs only
- [ ] Refactor or tests only

## Checklist

- [ ] `bun run test` (in `kiosk/`) and `python -m pytest` pass
- [ ] `ruff check ha-integration kiosk/tests kiosk/tools` is clean
- [ ] New behaviour has tests (unit for logic, browser test for anything you can see or tap)
- [ ] UI changes: screenshots regenerated with `python kiosk/tools/shots.py` (demo data only)
- [ ] No tokens, feed URLs, real names, IPs, Wi-Fi names, serials or MACs anywhere in the diff
- [ ] Works with no internet: no CDNs, web fonts or third-party calls added to the wall
- [ ] Tested on a real board (say which model), or explain why not
