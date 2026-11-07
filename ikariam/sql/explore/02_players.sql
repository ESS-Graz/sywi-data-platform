.read 00_setup.sql

-- Player profile per server on its latest snapshot day
SELECT country_code, server, count(*) AS players,
       round(median(account_age_days)) AS median_age_days,
       round(avg(city_count), 2) AS avg_cities,
       round(median(gold)) AS median_gold,
       round(max(population_total)) AS max_population
FROM latest_player
GROUP BY ALL
ORDER BY players DESC;

-- Government forms (numeric codes, not yet labelled)
SELECT government_form, count(*) AS players,
       round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct
FROM latest_player
GROUP BY 1
ORDER BY players DESC;

-- Do players with more cities have a larger population? (10 = 10 or more)
SELECT least(city_count, 10) AS cities_owned, count(*) AS players,
       round(avg(population_total)) AS avg_population
FROM latest_player
GROUP BY 1
ORDER BY 1;
