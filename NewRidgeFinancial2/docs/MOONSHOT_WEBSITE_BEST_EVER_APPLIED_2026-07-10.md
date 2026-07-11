# Moonshot AI — Best Dental Website Ever (APPLIED)

**Date:** 2026-07-10  
**Consult:** `MOONSHOT_WEBSITE_BEST_EVER_CONSULT_2026-07-10.md`  
**Site:** https://www.renodentalcare.org/  
**Status:** Phase 1 live; Phase 2–4 packaged (photo/video/PBHS/301s)

## Operator request

> proceed with all

## What went live (this apply)

| Item | Status |
|------|--------|
| Sticky mobile CTA bar (Call / Book / New Patients) | Live — mobile only (`#nr-sticky-cta`) |
| Stock / demo image purge CSS | Live — hides `rw-assets` stock + `demo-logo-2156` |
| Meet the Doctor = Dr. Reno sitting photo | Live (locked) |
| Homepage “New to New Ridge?” fast lane | Live |
| Homepage “Read Patient Reviews” CTA | Live |
| New Patient Experience hub | Live — `/patient-information/new-patients/` |
| Insurance & Payment hub (fixes prior 404 path) | Live — `/insurance-and-payment/` |
| Nav whitelist → show Insurance hub (`page-item-3205`) | Live |
| Soft-redirect location spam pages | Live — downtown / NW / south Wichita → hub cards |
| COVID-19 page | Soft-redirect content + **drafted** |
| Administrator Section (`admin2`) | **Drafted** (removed from public) |
| Patient Reviews boost CTA | Live |
| Prior redesign CSS (navy, hero, mega-nav, review title) | Retained + extended |

## Follow-up apply (same day — “do it”)

| Item | Status |
|------|--------|
| Mobile sticky Call/Book/New Patients verified | Confirmed on mobile viewport |
| Google Reviews CTA on Home + Patient Reviews | Live |
| Service-page “Ready to schedule this care?” CTAs | Live on 38 service pages |
| RevenueWell support ticket | Submitted via help.revenuewell.com as **mrenodds@hotmail.com** (check inbox for confirmation) |
| Mailto draft to support@pbhs.com / support@revenuewell.com | Opened on workstation |
| Photo booking checklist | `MOONSHOT_WEBSITE_BEST_EVER_PHOTO_BOOKING_CHECKLIST_2026-07-10.md` |

## Full-site content cleanup (all 92 pages)

| Action | Count |
|--------|-------|
| Soft-redirect thin SEO/utility pages → hubs | 18 |
| Rewrote thin/under-dev core pages (About, Preventive, Sedation, Gum, Reviews, policies, CareCredit) | 8 |
| Added/ensured visit CTA on remaining pages | 66 |
| Total pages updated | 92 |

Soft-redirect examples now live: `/blog-news/`, `/downtown-wichita-dentist/`, `/cosmetic-dentistry-2/`, `/pricing-cost-information/`, etc.

## Still needs people / PBHS response

1. **True DOM H1 rewrite** — awaiting PBHS/RevenueWell ticket.
2. **Hard 301s** — awaiting ticket.
3. **Photo/video shoot** — book using checklist (cannot schedule vendor without your calendar).
4. **Embedded Google Reviews widget** — link CTA live; full embed may need Business Profile widget setup.
5. **Multi-step forms** — PBHS capability.
6. **Platform migration** — only if unlock fails (Day 15 gate).

## Soft-redirected / drafted pages

**Soft-redirect (still published, content replaced with hub cards):**
- `/downtown-wichita-dentist/`
- `/dentist-in-northwest-wichita/`
- `/family-dentist-in-south-wichita/`
- `/covid-19/` (also drafted)

**Drafted (off public site):**
- `/admin2/`
- `/covid-19/`

## New / updated URLs to check

- https://www.renodentalcare.org/ — fast lane + reviews CTA + sticky on mobile
- https://www.renodentalcare.org/patient-information/new-patients/ — New Patient Experience hub
- https://www.renodentalcare.org/insurance-and-payment/ — Insurance hub
- https://www.renodentalcare.org/downtown-wichita-dentist/ — soft redirect hub

## Technical note

Overrides remain in page content as compact `<style id="nr-pro-sitewide">` + sticky `<nav>` on all published pages. Keep CSS **without blank lines** (wpautop).
