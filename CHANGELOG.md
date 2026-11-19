# Changelog

To update an installed copy, see "Already installed an older version?" in the
[README](README.md).

## 1.3.0
- Searches every airline through Google Flights, with Skyscanner as backup.
- Books on the official website of the airline flying your trip (built-in list of
  about 90 airlines). Travel sites like Expedia only if you name them. Search
  engines are never used to pay.
- Intake asks which saved traveler profile to use, plus cabin, preferred and
  avoided airlines. Defaults are shown in plain words.
- Dry run fills in every traveler's details and stops at the payment page.

## 1.2.0
- The agent can't skip you: trip details must come from you and you confirm a
  summary; search results must come from real, scanned pages; your pick is
  recorded in your own words.
- Official dry-run mode.
- Autopilot output is plain status data, so Muse's prompt-injection filter
  doesn't mistake it for an attack.

## 1.1.0
- Autopilot (`flightagent next`) runs the trip from the first question to the
  receipt.

## 1.0.0
- First release: trip spec checks, page scanning for prompt injection, look-alike
  site detection, hard-rule filter and ranking, pre-checkout gate, fare watch,
  receipt.
