# Why Do Players Start Donating?

This is an observational event analysis using `output/ikariam.lancedb`.

Definition used here:

> A **reliable donation start** is a player whose previous observed snapshot had `donations_total = 0`, and whose next observed snapshot is the first one with `donations_total > 0`.

That gives **21,515 observed zero-to-positive donation starts**. Another 25,924 donors were already positive in their first observed snapshot, so we cannot see their actual start.

## Main Conclusion

Players appear to start donating when they cross from isolated beginner play into island-based cooperative play.

The strongest signals are:

1. **They add a city.**
2. **They are on a populated island.**
3. **Their first donations are usually small and sawmill-focused.**

That fits the game rules: sawmills and luxury mines are shared island infrastructure, so donating starts to make sense once a player has a real stake in island production.

## 1. City Expansion Is The Strongest Trigger

Among zero-donation player states:

| next state | zero-player transitions | starts donating by next snapshot | start probability |
|---|---:|---:|---:|
| adds city by next snapshot | 23,942 | 12,217 | 51.0% |
| no city added | 80,348 | 9,659 | 12.0% |

Interpretation: adding a city is a major behavioral threshold. This may be because founding or developing another colony makes shared island infrastructure more valuable.

## 2. Most First Donations Happen Around 2-3 Cities

Reliable first donation events by city count:

| city bucket | starters | share | median first observed donation |
|---|---:|---:|---:|
| 1 city | 5,582 | 25.9% | 1,000 |
| 2-3 cities | 14,434 | 67.1% | 1,594 |
| 4-6 cities | 1,488 | 6.9% | 10,000 |
| 7-9 cities | 11 | 0.1% | 50,000 |

Interpretation: players usually start with small donations before they become large/mature players. Heavy donations come later.

## 3. Populated Islands Matter

Looking at the previous snapshot before donation starts:

| max island size player was on | starters | share |
|---|---:|---:|
| 1-2 island cities | 88 | 0.4% |
| 3-5 island cities | 226 | 1.1% |
| 6-10 island cities | 8,040 | 37.4% |
| 11+ island cities | 13,161 | 61.2% |

And as a start-probability comparison across all zero-donation states:

| max island size | zero-player transitions | starts next | start probability |
|---|---:|---:|---:|
| 1-2 island cities | 1,536 | 98 | 6.4% |
| 3-5 island cities | 3,391 | 231 | 6.8% |
| 6-10 island cities | 39,482 | 8,063 | 20.4% |
| 11+ island cities | 59,881 | 13,484 | 22.5% |

Interpretation: players are much more likely to start donating once they are on a busy island. That could mean better payoff, stronger social norms, or both.

## 4. First Donations Are Mostly To Sawmills

Reliable first donations by primary donation type:

| primary first-donation type | starters | share | median first observed donation |
|---|---:|---:|---:|
| sawmill primary | 14,975 | 69.6% | 1,500 |
| luxury mine primary | 5,256 | 24.4% | 2,346 |
| wonder primary | 1,284 | 6.0% | 298 |

Interpretation: first donations are practical infrastructure contributions. Players usually start with the basic shared production source: the sawmill.

## 5. Donor Share Alone Is Not A Clean Trigger

The island donor-share signal is noisy:

| max island donor-share bucket | zero-player transitions | starts next | start probability |
|---|---:|---:|---:|
| 0% | 3,217 | 763 | 23.7% |
| <50% | 36,412 | 9,823 | 27.0% |
| 50-75% | 43,251 | 7,889 | 18.2% |
| 75-99% | 21,410 | 3,401 | 15.9% |

This does **not** mean social norms do not matter. It means donor share is confounded by time, island maturity, and player lifecycle. Island population/density is the cleaner measurable trigger.

## Practical Hypothesis

The data supports this story:

> Players start donating when they become invested in an island economy. The common trigger is expansion, especially adding a new city or settling on a crowded island. The first donation is usually a small sawmill contribution, suggesting entry into the island’s cooperative production system rather than a large strategic investment.

## SQL: Reliable First Donation Events

```sql
LOAD lance;
ATTACH 'ikariam.lancedb' AS ikariam (TYPE lance);

WITH timeline AS (
  SELECT
    *,
    lag(donations_total) OVER (
      PARTITION BY country_code, player_id
      ORDER BY snapshot_date
    ) AS prev_donations,
    lag(snapshot_date) OVER (
      PARTITION BY country_code, player_id
      ORDER BY snapshot_date
    ) AS prev_snapshot_date
  FROM ikariam.main.player_snapshot
),
first_events AS (
  SELECT *
  FROM (
    SELECT
      *,
      row_number() OVER (
        PARTITION BY country_code, player_id
        ORDER BY snapshot_date
      ) AS rn_pos
    FROM timeline
    WHERE donations_total > 0
  )
  WHERE rn_pos = 1
),
reliable AS (
  SELECT *
  FROM first_events
  WHERE prev_snapshot_date IS NOT NULL
    AND coalesce(prev_donations, 0) = 0
)
SELECT
  CASE
    WHEN city_count = 1 THEN '1'
    WHEN city_count BETWEEN 2 AND 3 THEN '2-3'
    WHEN city_count BETWEEN 4 AND 6 THEN '4-6'
    ELSE '7+'
  END AS city_bucket,
  count(*) AS starters,
  round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS share_pct,
  round(quantile_cont(donations_total, 0.5), 0) AS median_first_observed_donation
FROM reliable
GROUP BY city_bucket
ORDER BY min(city_count);
```

## Caveats

- Snapshots are periodic, so we see the first **observed** positive donation, not the exact donation click.
- Donation values are cumulative, not individual donation events.
- We do not have chat, alliance membership, threats, pillaging, or explicit social pressure data.
- The analysis can identify strong behavioral signals, but not prove psychological intent.
