# Contributing to OpenFramely

Thanks for helping. This project frees a wall calendar from its vendor cloud, so the bar is simple: it must keep working with no internet, and it must never leak a family's data.

## Ground rules

- **Local first.** The wall talks to Home Assistant on the LAN. Do not add CDNs, web fonts, analytics or third-party calls in `kiosk/web/`.
- **No secrets or personal data in the repo.** Keep tokens, feed keys, serial numbers, MACs, IPs, Wi-Fi names, real names and photos with EXIF out of git. Use the demo household (Alex, Sam, Robin, Jamie, Riley, Casey) in docs, tests and screenshots.
- **Require a backup step before any eMMC write in PR instructions.** Bricking someone's calendar cannot be undone.
- **Keep it small.** Plain HTML/CSS/JS on the wall (no build step), pure Python logic in `logic.py`. Add a dependency when stdlib and existing code cannot cover the case.

## Getting set up

```sh
git clone https://github.com/spaceratz/openframely && cd openframely
cd kiosk && bun run test && cd ..          # wall unit tests (Bun)
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m playwright install chromium
python -m pytest                            # HA logic + browser tests
ruff check ha-integration kiosk/tests kiosk/tools
```

You don't need the hardware for most changes. The browser tests and `python kiosk/tools/shots.py` run the real wall page against a fake Home Assistant (`kiosk/tools/demo/mock.js`) at the wall's 1920x1080.

## Making a change

1. Open an issue first for anything bigger than a small fix, so we can agree the approach.
2. Branch from `main`: `feature/short-description` or `fix/short-description`.
3. Write or update tests:
   - Put pure helpers in `kiosk/web/lib.js` with tests in `kiosk/tests/lib.test.mjs`.
   - Put chore money, events and ICS logic in `logic.py` with tests in `ha-integration/tests/test_logic.py`.
   - Cover visible or interactive UI changes with a browser test in `kiosk/tests/test_e2e.py`.
4. If the UI changed, run `python kiosk/tools/shots.py` and commit the updated screenshots.
5. Use [Conventional Commits](https://www.conventionalcommits.org/): `feat: add week view`, `fix: garage label sticks on Opening...`.
6. Open a pull request and fill in the template. CI must be green.

## Code style

- JavaScript: 2-space indent, double quotes, semicolons, `const` by default, no frameworks. Keep the wall working on Android System WebView 109 (no `color-mix`, no `:has()` in critical paths).
- Python: `ruff` (config in `pyproject.toml`), type hints on public functions, no Home Assistant imports in `logic.py`.
- CSS: use the existing variables in `:root`. Keep touch targets at least 56px so small kids can tap them.
- Australian English in user-facing text.

## Reporting bugs and asking questions

- Bugs: use the **Bug report** issue form. Include your board model (`adb shell getprop ro.product.model`) and Home Assistant version.
- Ideas: use the **Feature request** form.
- Security problems: **don't open an issue**. See [SECURITY.md](SECURITY.md).

By contributing you agree your work is released under the [MIT licence](LICENSE) and that you'll follow the [Code of Conduct](CODE_OF_CONDUCT.md).
