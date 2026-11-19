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
Install this skill: https://raw.githubusercontent.com/Gokkul23/muse-flight-agent/708a0a2ac5ad20cb43af864b463d3b6f3b72f05f/skills/flight-booker/SKILL.md
Clone https://github.com/Gokkul23/muse-flight-agent at commit 708a0a2ac5ad20cb43af864b463d3b6f3b72f05f into your workspace.
Install exactly the files in the skill's "Files manifest" section, keeping paths.
Run its status check (selftest and the unit tests) and show me the real output.
If both pass, save flight-booker as a reusable skill for any request to find,
compare, book or watch flights.
```

Muse will ask you to approve the GitHub download; that approval comes from
Sentinel, which governs all network traffic out of the VM.

## 2. Traveler profile (memory, not files)

```
Remember a traveler profile called "family" for flight bookings:
- <full name exactly as on passport>, born <date of birth>
- <next traveler>, born <date of birth>
Booking contact: <email>, <phone>.
Needs: <meal / assistance needs, or none>.
```

## 3. Dry run first (real search, no payment)

```
Use flight-booker for a DRY RUN, run folder runs/dry-1. Run
python3 -m flightagent next and follow SKILL.md for each stage. Ask me every
trip question yourself and wait for my answers. Search the airline sites live.
```

Kattappa asks for the trip details, shows you a summary to confirm, compares
every airline on Google Flights, shows the approval cards, waits for your pick,
fills in your travelers on the airline's own site, checks the checkout page, and
stops at the payment page.

## 4. Book for real

```
Use flight-booker to book flights, run folder runs/family-maa. Run
python3 -m flightagent next and follow SKILL.md for each stage. Ask me every
trip question and wait for my answers.
```

Same flow, but at PAY it submits payment and Muse asks you to approve the exact
amount.

## 5. Watch the fare (optional)

```
Every day at 8am until <date>, run the flight-booker fare watch for
runs/family-maa. Message me only when it says to. Never rebook.
```

## 6. Receipt

```
Show me the receipt for runs/family-maa.
```
