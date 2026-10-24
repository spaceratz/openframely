# Security policy

## Reporting a vulnerability

Please **don't open a public issue** for security problems.

Report vulnerabilities through GitHub: go to the **Security** tab of this repository and choose **Report a vulnerability**. Include what you found, how to reproduce it, and what an attacker could do with it.

We acknowledge reports within 7 days, release fixes for confirmed issues as soon as practical, and credit reporters in the release notes unless you prefer to stay anonymous.

## Scope

In scope:

- The Home Assistant integration (`ha-integration/custom_components/family_kiosk`)
- The wall web app (`kiosk/web`) and the kiosk APK (`kiosk/android`)
- Anything in this repo that could leak a Home Assistant token, a Google feed key or a family's calendar

Out of scope:

- The vendor's original firmware and cloud service. Weaknesses there belong to the vendor to fix.
- Home Assistant itself (report to [Home Assistant](https://www.home-assistant.io/security/))

## Supported versions

We support the latest `main` branch.

## Hardening notes for users

- Give the wall a dedicated Home Assistant user with a long-lived token, and revoke it if the device is lost or sold.
- Keep the board's adb port (5555) reachable from your LAN only; this firmware has no adb authentication.
- Treat the Google Apps Script feed URL as a password, because it contains the feed key.
