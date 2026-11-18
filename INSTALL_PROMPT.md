# Running this in Muse

Muse gives each user a dedicated Linux VM with a browser, storage and the ability
to compile and run code, build skills, run sub-agents and scheduled jobs
([Meta](https://muse.ai/blog/security-and-safety-for-ai-agents-our-approach-with-muse)).
Muse does not have an official "upload a skill" button. Community skills are
installed by pointing Muse at a pinned `SKILL.md`, asking it to install the
files in its manifest and run the skill's status check. That is the path below.

Read the repo before you install it. Treat any public skill, including this one,
as code you choose to run.

## 1. Install

Pin a release so what you install is what you read:

```
Install this skill: https://raw.githubusercontent.com/Gokkul23/muse-flight-agent/001e69f1804c6ff4002e0ce792eb6a4a3712fec4/skills/flight-booker/SKILL.md
Clone https://github.com/Gokkul23/muse-flight-agent at commit 001e69f1804c6ff4002e0ce792eb6a4a3712fec4 into your workspace.
Install exactly the files in the skill's "Files manifest" section, keeping paths.
Run its status check (selftest and the unit tests) and show me the real output.
If both pass, save flight-booker as a reusable skill for any request to find,
compare, book or watch flights.
```

Muse will ask you to approve the GitHub download; that approval comes from
Sentinel, which governs all network traffic out of the VM.

## 2. Traveler profile (memory, not files)

```
Remember a traveler profile called "family": <names exactly as on passports>.
<meal / assistance needs>. Use this profile only for flight bookings.
```

## 3. Book

```
Use flight-booker to book flights for my family, run folder runs/family-maa.
Run the autopilot (flightagent next) and follow it until DONE. Ask me what you
need to know in one message.
```

That's it. The agent asks you for the trip details, searches, shows you the
best options, asks you to pick, checks the checkout page, and submits payment.
Muse then asks you to approve the exact amount.

## 4. Watch the fare (optional)

```
Every day at 8am until <date>, run the flight-booker fare watch for
runs/family-maa. Message me only when it says to. Never rebook.
```

## 5. Receipt

```
Show me the receipt for runs/family-maa.
```
