# Python v2 vs SQL Gold Verification

Tolerance: `1e-06` absolute.
SQL gold CSVs are the exported outputs from `Alle_Queries_DE_hintereinander.sql`.
Comparison uses rows with common keys and ignores SQL NULL-shell values.

## player_latest vs A_DS.csv
- Python rows: 21,822
- SQL rows: 21,829
- Common keys: 21,822
- Python-only keys: 0
- SQL-only keys: 7
- SQL-only key sample: player_id=34bbacfe70afdedba45e81e64f1a401884893dce; player_id=414cf37d224866c57fce4fac3c1144f553e0bbb9; player_id=60eec3b3112b489daefec2e4440b05473a5302f3; player_id=615700549e2b861fda9523afd0b800f04005f913; player_id=7452df42ec566caf3dc839b67fe6fba436c2b93d; player_id=9086bfe9111b5af5da50595e21e94295e70dc4a3; player_id=c9c68c136b18fe14f3e6e94f25e44d39b2ebe40e
- Compared mapped columns: 20
- Result: PASS

## player_island_latest vs AVI_DS.csv
- Python rows: 41,079
- SQL rows: 41,086
- Common keys: 41,079
- Python-only keys: 0
- SQL-only keys: 7
- SQL-only key sample: player_id=34bbacfe70afdedba45e81e64f1a401884893dce, island_id=6d8fcc3a86a6a845735ab04bffb87281f4e306fb; player_id=414cf37d224866c57fce4fac3c1144f553e0bbb9, island_id=6d8fcc3a86a6a845735ab04bffb87281f4e306fb; player_id=60eec3b3112b489daefec2e4440b05473a5302f3, island_id=001f45b03915e055744c035af0e1e2f7025affbc; player_id=615700549e2b861fda9523afd0b800f04005f913, island_id=335ad7fd36eabe8a88da866716a574204de5445b; player_id=7452df42ec566caf3dc839b67fe6fba436c2b93d, island_id=ade78558350cc7c214f25204d652ad819cad5038; player_id=9086bfe9111b5af5da50595e21e94295e70dc4a3, island_id=8e6a7afa7a4925324254957136b87263c321f449; player_id=c9c68c136b18fe14f3e6e94f25e44d39b2ebe40e, island_id=d241fc17983f5cc9662c87bdd9a68b8fb1cd0698
- Compared mapped columns: 14
- Result: PASS

## island_latest vs I_DS.csv
- Python rows: 5,351
- SQL rows: 5,351
- Common keys: 5,351
- Python-only keys: 0
- SQL-only keys: 0
- Compared mapped columns: 19
- Result: PASS

## player_summary vs Teilnahme_AV.csv
- Python rows: 21,822
- SQL rows: 21,829
- Common keys: 21,822
- Python-only keys: 0
- SQL-only keys: 7
- SQL-only key sample: player_id=34bbacfe70afdedba45e81e64f1a401884893dce; player_id=414cf37d224866c57fce4fac3c1144f553e0bbb9; player_id=60eec3b3112b489daefec2e4440b05473a5302f3; player_id=615700549e2b861fda9523afd0b800f04005f913; player_id=7452df42ec566caf3dc839b67fe6fba436c2b93d; player_id=9086bfe9111b5af5da50595e21e94295e70dc4a3; player_id=c9c68c136b18fe14f3e6e94f25e44d39b2ebe40e
- Compared mapped columns: 1
- Result: PASS

## player_island_summary_for_sql vs Master_Avi.csv
- Python rows: 41,079
- SQL rows: 41,086
- Common keys: 41,079
- Python-only keys: 0
- SQL-only keys: 7
- SQL-only key sample: player_id=34bbacfe70afdedba45e81e64f1a401884893dce, island_id=6d8fcc3a86a6a845735ab04bffb87281f4e306fb; player_id=414cf37d224866c57fce4fac3c1144f553e0bbb9, island_id=6d8fcc3a86a6a845735ab04bffb87281f4e306fb; player_id=60eec3b3112b489daefec2e4440b05473a5302f3, island_id=001f45b03915e055744c035af0e1e2f7025affbc; player_id=615700549e2b861fda9523afd0b800f04005f913, island_id=335ad7fd36eabe8a88da866716a574204de5445b; player_id=7452df42ec566caf3dc839b67fe6fba436c2b93d, island_id=ade78558350cc7c214f25204d652ad819cad5038; player_id=9086bfe9111b5af5da50595e21e94295e70dc4a3, island_id=8e6a7afa7a4925324254957136b87263c321f449; player_id=c9c68c136b18fe14f3e6e94f25e44d39b2ebe40e, island_id=d241fc17983f5cc9662c87bdd9a68b8fb1cd0698
- Compared mapped columns: 2
- Result: PASS
