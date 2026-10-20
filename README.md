# Salud

A daily health diary that tells me when I drift away from my own normal.

Generic thresholds ("a resting heart rate above X is high") say very little about one specific body. So I built a diary that collects my own data every day, from a smart ring, my phone, the weather and what I eat, and compares each night with my own recent baseline instead of a population average. It's for spotting deviations, not for diagnosing anything. The first months are about collecting clean data, and any predictive model has to earn its place against simple rules.

## What it does

- A daily journal: how I feel, symptoms, meals through the day, context, caffeine, alcohol and exercise. It autosaves and shows a calendar of filled days.
- A ring tab that writes last night's sleep, heart rate, HRV, respiration, skin temperature and blood oxygen as plain sentences against "what is normal for you".
- A phone tab that turns screen sessions and unlocks into bedtime and wake-up estimates, night-time pickups and screen time before sleep.
- Daily weather and air quality, fetched automatically.
- Each meal broken into estimated nutrients and simple flags (fried, ultra-processed, fruit and vegetables), compared with daily targets.
- An installable PWA with CSV export, served from a small server of my own.

## How the baseline works

This is what the code does today (see [`excerpts/baseline.py`](excerpts/baseline.py), which runs on synthetic data).

For every signal, the baseline is built only from previous nights: up to the last 14, counting only nights with at least four hours of sleep. The night being judged never enters its own baseline. The baseline is the median plus a usual range, the 10th to 90th percentile with seven or more nights and min to max with fewer. With fewer than three usable nights it doesn't compare anything and says it's still calibrating. Inside the range, a value is normal. Outside it, the app says how far it is from the median and what the usual range is, in plain words. Changing device creates a new baseline.

The phone side uses the same idea: a "night" is the longest stretch without real phone use, with short interruptions merged in.

Planned but not built: z-scores and a CUSUM detector for slow drifts, and a machine-learning model that would run in shadow mode until there's enough labelled data to compare it fairly with the rules. A table already stores each morning's verdict, frozen, so it can be audited later.

## Under the hood

Everything is stored append-only in one SQLite file: raw downloads are kept verbatim with a checksum, and derived rows are upserted idempotently from a field mapping, so past states can be reconstructed. One Python process (standard library only) serves the API and the PWA, and scheduled jobs pull the external sources. See [`excerpts/schema.py`](excerpts/schema.py) and [`excerpts/ingest.py`](excerpts/ingest.py). The excerpts are adapted for readability and use synthetic data only.

Since it's health data, it stays private. It lives on my own server behind HTTPS and authentication, the phone app can only send data and not read it back, and there's no analytics or cloud sync. The database and credentials are never in this repo.

## Built with

Python (standard library), SQLite, vanilla HTML, CSS and JavaScript, a service worker, nginx, systemd, and a small native Android app for phone uploads.

## Where it is

In daily use, still collecting data. Next come a baseline view once there are enough weeks, simple alert rules, and only then a first model.

Salud is a personal project, not a medical device, and it shouldn't be used for medical decisions.

---

The full source is private. This repo shows how it works and a few pieces of the code; happy to walk through the rest.

© 2026 Arnau Mas
