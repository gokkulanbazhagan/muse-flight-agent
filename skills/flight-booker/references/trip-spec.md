# Trip spec reference

The trip spec is a JSON file the user writes once and reuses. It holds the goal,
the hard constraints, the soft preferences and the stop conditions. It must not
hold identity documents or payment details.

## Fields

| Field | Type | Meaning |
|---|---|---|
| `trip_name` | string | Free label, used in run logs. |
| `travelers` | int | Number of seats to book. |
| `traveler_profile` | string | Pointer to the memory entry with names and DOBs, e.g. `"memory:parents"`. |
| `origin` / `destination` | IATA codes | e.g. `"SFO"`, `"MAA"`. |
| `depart_window` | `[start, end]` ISO dates | Earliest and latest departure date. |
| `hard.max_stops` | int | Itineraries with more stops are rejected. |
| `hard.min_layover_min` / `hard.max_layover_min` | int | Every connection must fall inside this range. |
| `hard.max_total_duration_min` | int | Door-to-door flying plus layovers. |
| `hard.checked_bags_per_traveler` | int | Included bags required. |
| `hard.price_cap_total` | number | Cap for all travelers, taxes and fees included. |
| `hard.currency` | string | Currency of the cap. |
| `hard.no_redeye` | bool | Rejects departures between 23:00 and 05:00 local. |
| `hard.seats_together` | bool | Requires the seller to show adjacent seats available. |
| `hard.require_self_transfer_free` | bool | Rejects itineraries on separate tickets. |
| `soft.weights` | object | Weights for `duration`, `price`, `layover_comfort`, `carrier_rating`. |
| `soft.preferred_carriers` | list | Small bonus, never overrides a hard rule. |
| `services` | list | e.g. `["VGML", "WCHR"]` (meal and assistance codes to request after booking). |
| `allowed_sellers` | list | Domains the agent may check out on. |
| `max_price_drift_pct` | number | Stop if the price moves more than this between shortlist and checkout. |

## Candidate shape

Each candidate the agent collects:

```json
{
  "id": "c1",
  "seller": "aa.com",
  "carrier": "AI",
  "total_price": 1840.00,
  "currency": "USD",
  "checked_bags_per_traveler": 2,
  "seats_together_available": true,
  "single_ticket": true,
  "carrier_rating": 4.1,
  "price_seen_at": "2026-11-10T14:05:00-08:00",
  "segments": [
    {"flight": "AI176", "from": "SFO", "to": "BOM",
     "depart_local": "2026-11-20T11:30", "arrive_local": "2026-11-21T19:10",
     "duration_min": 1000}
  ],
  "layovers_min": []
}
```

`layovers_min` has one entry per connection, in minutes.
