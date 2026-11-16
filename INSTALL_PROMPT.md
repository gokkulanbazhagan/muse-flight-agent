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

Pin a commit so what you install is what you read:

```
Install this skill: https://raw.githubusercontent.com/Gokkul23/muse-flight-agent/<commit-sha>/skills/flight-booker/SKILL.md
Clone https://github.com/Gokkul23/muse-flight-agent at that commit into your workspace.
Install exactly the files in the skill's "Files manifest" section, keeping paths.
Run its status check (selftest and the unit tests) and show me the real output.
If both pass, save flight-booker as a reusable skill for any request to find,
compare, book or watch flights.
```

Muse will ask you to approve the GitHub download; that approval comes from
Sentinel, which governs all network traffic out of the VM.

## 2. Traveler profile (memory, not files)

```
Remember a traveler profile called "parents": two adults, names exactly as on
their passports: <name 1>, <name 2>. Vegetarian meals (VGML) and wheelchair
assistance at airports (WCHR). Use this profile only for flight bookings.
```

You can review or edit it later in Muse's memory settings.

## 3. Trip spec

```
Create trip_spec.json from examples/trip_spec.example.json with these changes:
<dates, airports, cap, sellers>. Run check-spec and show me the result.
```

## 4. Book

```
Use flight-booker for trip_spec.json with run folder runs/parents-maa.
Follow the skill exactly. Show me the approval cards and wait for my pick.
```

## 5. Watch the fare (optional)

```
Every day at 8am until <date>, run the flight-booker fare watch for
runs/parents-maa. Message me only when the CLI exits 2. Never rebook.
```

## 6. Receipt

```
Show me the receipt for runs/parents-maa.
```
