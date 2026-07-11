# Moonshot AI — Best Dental Website Ever (FULL-SITE CONSULT)

**Date:** 2026-07-10  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Site:** https://www.renodentalcare.org/  
**Platform:** PBHS WordPress (admin `/admin`)  
**Pages evaluated:** 93 (inventory attached)  
**Script:** `scripts/run_moonshot_website_best_ever_consult.py`  
**Apply:** DO NOT EDIT LIVE until operator approves specific phases.

## Operator request (verbatim)

> ask moonshot ai to evaluate my website with all the page and ask what can be done to macke it the best dental office website EVER!

---

# Verdict — Can this become best-in-class? 
**YES** — but only if you escape the PBHS "dental website template" gravity well. You have the core ingredients: a real doctor with a real face (Dr. Reno), a real office (North Ridge Rd), genuine patient relationships, and a service area (Wichita metro) with clear identity. The 2026-07-10 CSS overrides prove you can bend Template2120 toward brand authenticity. However, 93 thin pages, stock-photo leakage, and layoutAccess limitations create a ceiling. To become "best ever," you must consolidate ruthlessly, shoot proprietary photography, and either force PBHS into submission or migrate.

## 0. Operator Intent
Transform New Ridge Family Dental from a "template-based practice site" into the definitive digital experience for family dentistry in Wichita — prioritizing patient trust, frictionless conversion, and local authority over keyword-stuffed SEO spam.

## 1. Scorecard (1–10)
| Category | Score | Rationale |
|----------|-------|-----------|
| **Design** | 5/10 | Navy overlay improves brand, but Template2120 bones show; stock photo leakage; dense mid-page card stacks create cognitive load |
| **Trust** | 6/10 | Real Dr. Reno photo locked in; office photos exist; review carousel present but CTAs hidden; still fighting PBHS demo assets |
| **Conversion** | 4/10 | "Book Now" likely buried in dense nav; no clear new-patient fast lane; membership popup present but intrusive; phone number not sticky |
| **IA** | 3/10 | 93 pages is digital hoarding; duplicate content (Cosmetic Dentistry x2, Contact Us x2); thin location spam pages; broken insurance link |
| **Content** | 4/10 | SoftDent-style service descriptions; no video; H1/DOM mismatch for accessibility; "under development" vibes on utility pages |
| **Mobile** | 5/10 | Responsive but not thumb-optimized; portal cards likely too small; hero text may overlay poorly on small screens |
| **Local SEO** | 5/10 | Citations likely consistent, but keyword cannibalization across 93 pages dilutes authority; missing GMB integration |
| **Differentiation** | 4/10 | "Comfort-Focused" vs "Modern Family Dentistry" identity crisis; still looks like 1,000 other PBHS sites despite color changes |

## 2. What Already Improved (Credit Due)
**Do not undo this work:**
- **Brand Color Lock**: Navy #1E3A5F establishes authority (medical + trust)
- **Hero Simplification**: Single office photo vs. chaotic collage eliminates "cheap template" signal
- **Navigation Hygiene**: Mega-nav SEO strip hidden; primary nav reduced to 6 items (cognitive relief)
- **Doctor Humanization**: `blueeyes_77f17b.png` locked as Dr. Reno banner; no more rotating stock woman
- **Social Proof Framing**: "What Wichita Families Are Saying" localizes reviews vs. generic "Testimonials"
- **CSS Override Architecture**: `<style id="nr-pro-sitewide">` proves you can iterate without layoutAccess
- **Geographic Eyebrow**: Wichita · Andover · Goddard establishes immediate relevance

## 3. Full-Site Critique — Page by Page Type

### Homepage (`/`, `/home/`)
- **Broken**: DOM H1 "Comfort-Focused Family Dentistry" mismatches visual overlay "Modern Family Dentistry" (accessibility/SEO fail)
- **Weak**: Mid-page portal stack (likely 6+ action cards) creates decision paralysis; video strip slows load
- **Stock Leakage**: `photo609`, `photo579`, `demo-logo-2156-lg.png` still referenced in HTML
- **Missing**: No sticky CTA; no "New Patient? Start Here" fast lane; no trust badges (ADA, Academy memberships)

### Services Architecture (`/services-treatments/` + 40+ service pages)
- **Catastrophic Bloat**: SoftDent-style taxonomy created 40+ thin pages (Amalgam Fillings, Soft Liners, Rebase & Repairs as standalone pages)
- **Cannibalization**: "Cosmetic Dentistry" exists at `/cosmetic-dentistry/` and `/cosmetic-dentistry-2/`
- **Content Quality**: Likely manufacturer-provided copy; no Dr. Reno voice; no case studies
- **Conversion**: No "Book This Service" contextual CTAs; generic contact forms only

### New Patient Journey (4+ fragmented pages)
- **Fragmentation**: `/new-patients/`, `/new-patient-information/`, `/first-visit/`, `/new-patient-prep-guide/`, `/scheduling/` — too many decision points
- **Friction**: No online booking (assumed); forms likely PDF-based; no insurance verification tool
- **Opportunity**: Merge into single "New Patient Experience" authority page with tabbed navigation

### Insurance & Payment
- **Critical 404**: `/insurance-and-payment/` (nav link) returns 404; actual page likely at `/insurance-payment-options/` or `/financing-insurance-options/`
- **Trust Gap**: No specific insurance list (Delta, Cigna, etc.); no "We maximize your benefits" copy; CareCredit buried at `/care-credit/`

### Doctor/Team (`/dr-michael-reno/`, `/meet-the-staff/`, `/our-team/`)
- **Win**: Real portrait in content
- **Loss**: Likely no video intro; no "Why I became a dentist" story; no CV/credentials download; staff photos likely missing or stock

### Reviews (`/patient-reviews/`, `/patient-testimonials-reviews/`)
- **Function**: Carousel exists but "Read More" CTAs hidden (good for stopping leakage, bad for engagement)
- **Missing**: Video testimonials; Google Reviews embed; before/after case stories; no "Leave a Review" CTA for patients

### Location/SEO Spam Pages
- **Kill List**: `/downtown-wichita-dentist/`, `/dentist-in-northwest-wichita/`, `/family-dentist-in-south-wichita/` — thin content, Panda bait
- **Strategy**: 301 redirect to single "Wichita Family Dentist" pillar page with neighborhood context (Riverside, College Hill, etc.)

### Utility/Policy Pages
- **Bloat**: `/covid-19/` (outdated?), `/admin2/` (security risk?), `/introduction/` (duplicate Welcome)
- **Missing**: `/accessibility/` statement; `/sitemap/` likely auto-generated and overwhelming

## 4. Best-Dental-Website-Ever Standard — The Bar
1. **3-Second Clarity**: Patient knows it's a Wichita family dentist, sees real faces, and can book in one tap
2. **Zero Stock Photography**: Every image is Dr. Reno, his team, his patients (with releases), or his actual office
3. **Single-Page New Patient Flow**: All first-visit info, forms, insurance verification, and booking in one scrollable experience
4. **Video-First Social Proof**: 60-second welcome from Dr. Reno + patient video testimonials (not carousels)
5. **Semantic HTML**: One H1 per page, logical heading order, alt tags, WCAG 2.1 AA contrast ratios
6. **Sub-2-Second Load**: No hero sliders, optimized images, no render-blocking scripts
7. **Contextual Conversion**: "Schedule Cleaning" vs. "Schedule Implant Consult" vs. "Schedule Child's First Visit" — specific CTAs per service
8. **Transparent Pricing**: Real fee ranges or "Insurance usually covers X%" language; membership plan calculator
9. **Local Ownership**: Dominates "Wichita dentist" not through 93 spam pages but through 3 authoritative pillars (Services, New Patients, About)
10. **Post-Appointment Loop**: Patient portal integration, review request automation, referral program visibility

## 5. Gap Analysis — Current vs. Best Ever
| Best Ever Principle | Current State | Gap |
|---------------------|---------------|-----|
| 3-Second Clarity | Hero improved but H1 hidden; nav still dense | **MUST**: Fix H1 hierarchy; sticky "Book" button |
| Zero Stock Photos | CSS locked hero but leakage in components | **MUST**: Photo shoot; CSS purge of `photo609` etc. |
| Single-Page New Patient | 5+ fragmented pages | **MUST**: Consolidate to `/new-patient-experience/` |
| Video-First | No video presence | **SHOULD**: Produce Dr. Reno welcome video |
| Semantic HTML | H1/DOM mismatch | **MUST**: PBHS ticket to edit source H1s |
| Sub-2-Second | PBHS bloat + 93 pages | **SHOULD**: Page consolidation reduces crawl budget |
| Contextual CTAs | Generic "Contact Us" | **SHOULD**: Service-specific booking intents |
| Transparent Pricing | `/pricing-cost-information/` likely thin | **NICE**: Interactive estimator tool |
| Local Ownership | 3 location spam pages | **MUST**: 301 merge to single pillar |
| Post-Appointment | Patient Portal link exists | **NICE**: Review automation integration |

## 6. Primary Design + Brand Direction (World-Class)
**Brand Essence**: "The Ridge Standard" — Modern precision meets family warmth. Wichita's neighborhood dental home where advanced technology (AI radiographs) is delivered with genuine Kansas hospitality.

**Visual System**:
- **Primary**: Navy #1E3A5F (authority, medical trust) — keep this
- **Secondary**: Warm Sand #F5F1EB (comfort, anti-clinical)
- **Accent**: Copper/Rust #B87333 (Wichita aviation heritage, warmth)
- **Typography**: Clean sans-serif for UI (Inter or system-ui), serif for editorial trust (Playfair Display for Dr. Reno quotes)
- **Photography Style**: Natural light, shallow depth of field, real patients laughing (not "open mouth" clinical shots), Dr. Reno in blue scrubs (not white coat barrier), team candid moments, Wichita skyline subtly in background of window shots

**Interaction Design**:
- **No sliders**. Ever. Single hero image with parallax subtlety.
- **Sticky bottom bar** on mobile: "Call" | "Text" | "Book" (thumb-zone)
- **Card-based service browser**: Icon + 2-line description + "Learn more" (not walls of text)

## 7. Information Architecture — Ideal Sitemap (Consolidate 93 → 18)
**KEEP (Consolidated)**:
1. **Home** (`/`) — Trust + Navigation hub
2. **Services** (`/services/`) — Hub with 6 category cards (Preventive, Restorative, Cosmetic, Implants, Sedation, Kids)
3. **New Patient Experience** (`/new-patients/`) — Merge: First Visit, Prep Guide, Scheduling, Registration, Insurance Verification
4. **Meet Dr. Reno** (`/dr-michael-reno/`) — Merge: Our Team, Why Choose Dr. Reno, credentials, video
5. **Patient Stories** (`/reviews/`) — Merge: Reviews, Success Stories, Before/After (with consent)
6. **Office Tour** (`/office/`) — Merge: Office Photos, Virtual Tour, Technology (AI Radiographs)
7. **Insurance & Care** (`/insurance/`) — Merge: Insurance Options, CareCredit, No Insurance Membership, Financial Policy
8. **Contact / Location** (`/contact/`) — Merge: Contact Us variations, Map, Hours
9. **Blog** (`/blog/`) — Merge: Blog & News, Patient Education (actual content marketing, not SEO spam)
10. **Emergency** (`/emergency/`) — Dental Emergencies (keep for high-intent searches)

**KILL (301 Redirect)**:
- All 3 location spam pages → merge into `/about/our-wichita-community/`
- Duplicate cosmetic pages → canonical to `/services/cosmetic/`
- SoftDent minutiae (Soft Liners, Rebase) → consolidate into `/services/dentures/` sections
- COVID-19 page (outdated) → redirect to Home
- Admin-facing pages (`/admin2/`) → password protect or remove from index

**RESULT**: ~18 high-authority pages vs. 93 thin pages. Better UX, better SEO crawl efficiency.

## 8. Homepage Spec — First Viewport + Below Fold

### Viewport 1 (Hero) — 100vh
```
[Background: Full-bleed office exterior or reception area — natural light, welcoming]
[Overlay: Semi-transparent navy gradient bottom 40%]

Eyebrow (Small caps, copper): WICHITA FAMILY DENTISTRY SINCE [YEAR]

H1 (White, bold): Modern Dental Care for Wichita Families

Subhead (White, 60% opacity): Comprehensive preventive, restorative, and cosmetic dentistry 
for every generation — from first smiles to lasting health.

[CTA Row]
[Primary Button: Navy background, white text] Schedule Your Visit →
[Secondary Button: Transparent, white border] Call (316) 722-6060

[Trust Bar — absolute bottom, white background]
Delta Dental • Cigna • Guardian • CareCredit Accepted | ★★★★★ 200+ Google Reviews
```

### Viewport 2 — The Ridge Difference (3-Column Grid)
```
[Card 1: Photo of Dr. Reno]
Headline: Meet Dr. Michael Reno
Body: Wichita native, [X] years serving Ridge Road families, committed to comfort-first care.
Link: Get to know our dentist →

[Card 2: Photo of technology]
Headline: AI-Assisted Diagnosis
Body: Early detection with 90% more accuracy using artificial intelligence radiography.
Link: See our technology →

[Card 3: Photo of family]
Headline: No Insurance? No Problem.
Body: Membership plans starting at $[X]/month include cleanings, exams, and discounts.
Link: Explore membership →
```

### Viewport 3 — Social Proof
```
Headline: Trusted by 2,000+ Wichita Families

[Video Grid — 3 patient testimonial thumbnails, not autoplay]

[Stats Bar]
4.9★ Google Rating | 15+ Years Serving Wichita | Same-Day Emergency Appointments
```

### Viewport 4 — Services Preview (Horizontal Scroll on Mobile)
```
Headline: Care for Every Smile

[Cards: Cleanings, Crowns, Implants, Whitening, Sedation — icon + title + "Learn more"]
[Final Card]: View All Services →
```

### Viewport 5 — New Patient Fast Lane
```
Headline: New to New Ridge?

[3-Step Visual]
1. Book Online or Call → 2. Insurance Verification → 3. Relax & Receive Care

[CTA]: Start Your First Visit (links to consolidated /new-patients/)
```

### Footer
```
[Left Column]
New Ridge Family Dental
2135 North Ridge Rd Ste 700
Wichita, KS 67212
(316) 722-6060
Mon–Thu: 7am–4pm

[Middle Column]
[Map embed — small]

[Right Column]
Quick Links: New Patients | Financial Info | Reviews | Contact

[Bottom Bar]
© 2026 New Ridge Family Dental | Accessibility | Privacy | Sitemap
```

## 9. Page-Type Specs

### Services Hub (`/services/`)
- **Layout**: Grid of 6 category cards (not 40+ links)
- **Each Card**: Icon, title, 2-line description, "Explore" link
- **Below Fold**: "Not sure what you need? Schedule a complimentary consultation" (lead gen)
- **Content**: Dr. Reno explains each category in his own words (video or quote), not manufacturer copy

### New Patient Experience (`/new-patients/`) — THE MONEY PAGE
- **Hero**: Smiling patient (real) with headline "Your First Visit, Simplified"
- **Tabbed Interface**:
  - Tab 1: What to Expect (step-by-step, timeline)
  - Tab 2: Patient Forms (downloadable PDFs + digital forms if PBHS allows)
  - Tab 3: Insurance (real-time verification tool or "We accept..." list)
  - Tab 4: Financing (CareCredit + Membership Plan details)
- **Sticky CTA**: "Ready to join our dental family? [Book Now]"

### Dr. Reno Page (`/dr-michael-reno/`)
- **Hero**: Video background of Dr. Reno speaking to camera (60 seconds)
- **Credentials**: DDS, continuing education, memberships (ADA, Kansas Dental Association)
- **Personal**: "Why I chose dentistry" story, family photo (if comfortable), community involvement
- **Team Grid**: Hygienists, assistants, admin — names, photos, "favorite part of working at New Ridge"

### Reviews (`/reviews/`)
- **Embedded Google Reviews** (live feed via API/widget)
- **Video Testimonials**: 3-5 patients (variety: implant patient, mom with kids, anxious patient)
- **Before/After Gallery**: With written consent, procedure notes, timeline
- **CTA**: "Join our family of happy patients [Book]"

### Contact (`/contact/`)
- **Sticky Info**: Address, phone, hours at top (not buried)
- **Map**: Google Maps embed with photo of building exterior ("Look for the navy awning")
- **Form**: Name, Phone, Email, Preferred Day/Time, Reason for Visit (dropdown), Insurance Carrier
- **Emergency Banner**: "Dental Emergency? Call (316) 722-6060 — Same-day appointments available"

### Insurance (`/insurance/`)
- **Accepted Plans**: Visual logos of Delta, Cigna, Guardian, MetLife, etc.
- **Membership Plan**: "No Insurance? Perfect!" content moved here (not popup), pricing table, comparison vs. traditional insurance
- **Verification**: "Verify your benefits" form (name, DOB, insurance ID, submit for callback)

## 10. Content & Photography Plan

**MUST Shoot (Wichita Location)**:
1. **Dr. Reno**: Headshots (white coat + scrubs), candid with patient (consent), at desk reviewing X-rays, laughing with team
2. **Team**: Group photo outside office with "New Ridge" signage, individual portraits with personal props (hobbies)
3. **Office**: Wide shots of reception (natural light), operatories (show technology, not just chair), sterilization area (trust), kids' corner
4. **Patients**: 5-10 diverse real patients (signed releases) for hero images, testimonials
5. **Details**: Close-ups of AI radiograph screen, CareCredit tablet, coffee station (comfort details)

**Video Content**:
- **Dr. Reno Welcome** (90 seconds): Standing in office, introducing philosophy
- **Office Tour** (2 minutes): Walkthrough showing cleanliness and technology
- **Patient Testimonials** (3 x 60 seconds): Different procedures, emotional payoff

**Copy Voice**:
- **Tone**: Warm, confident, jargon-free. "We explain, never lecture."
- **Avoid**: "Comprehensive dental solutions utilizing state-of-the-art..." (robot speak)
- **Use**: "We use the same technology you'd find at the best Wichita hospitals, explained in plain English."

## 11. Conversion System — CTAs, Forms, Phone, Portal, Membership

**CTA Hierarchy**:
1. **Primary**: "Schedule Your Visit" (soft, inviting) — links to /new-patients/
2. **Secondary**: "Call (316) 722-6060" — tel: link
3. **Tertiary**: "Text Us" — if PBHS supports SMS, or Google Business Messages integration

**Forms Optimization**:
- **Current**: Likely generic PBHS forms
- **Upgrade**: Multi-step form (Step 1: Name/Contact, Step 2: Insurance, Step 3: Preferred Times)
- **Confirmation**: "Thanks! We'll text you within 2 hours to confirm your appointment."

**Phone Strategy**:
- **Sticky Header**: Phone number visible at all times on mobile
- **Click-to-Call**: All phone numbers hyperlinked
- **Tracking**: Use different numbers for website vs. Google My Business to measure attribution (CallRail or similar)

**Membership Program**:
- **Current**: Popup intrusion
- **Upgrade**: Dedicated page + sidebar on Insurance page + mentioned in "No Insurance?" service cards
- **Pricing**: Transparent table showing what's included (2 cleanings, 1 exam, X-rays, 15% off procedures)

**Patient Portal**:
- **Current**: Link likely buried
- **Upgrade**: "Patient Login" in top right corner (utility nav), with screenshot of what they can do (pay bill, see X-rays, request appointments)

## 12. Technical / PBHS Constraints & Required Tickets

**Critical PBHS Tickets Needed**:
1. **H1 Source Edit**: Request PBHS edit Template2120 to change actual DOM H1 from "Comfort-Focused..." to "Modern Family Dentistry in Wichita" (or remove hidden CSS reliance)
2. **Layout Access**: Request `layoutAccess=true` for admin account to edit Layout parts without CSS hacks
3. **404 Fix**: Correct `/insurance-and-payment/` slug to match nav or update nav to `/insurance-payment-options/`
4. **Image Purge**: Remove `demo-logo-2156-lg.png` and stock `photo609/photo579` from media library and template references
5. **Page Consolidation**: Request 301 redirect implementation for the ~75 pages being killed (or provide .htaccess rules if you have server access)
6. **Form Optimization**: Enable multi-step form functionality or custom form builder access
7. **Speed Optimization**: Enable image lazy loading, minify CSS/JS (PBHS often bloated)
8. **Schema Markup**: Verify LocalBusiness, Dentist, and Service schema implemented

**CSS Workarounds (Until Tickets Resolved)**:
- Continue using `<style id="nr-pro-sitewide">` for hero locks and stock photo hiding
- Use `!important` sparingly but effectively to override Template2120 defaults
- Monitor for PBHS updates that may overwrite custom CSS (version control your overrides)

**Platform Exit Strategy**:
If PBHS cannot accommodate requirements (custom post types, reduced page count, true H1 control), plan migration to:
- **WordPress (Custom)**: Full control, but requires maintenance
- **Webflow**: Design flexibility, good CMS for 18-page architecture
- **Squarespace 7.1**: If simplicity prioritized, but less dental-specific
- **Weave/DoctorLogic**: Dental-specific but review contracts carefully for content ownership

## 13. Phased Roadmap to "Best Ever"

### Phase 1: Foundation Repair (Days 1–30)
**Goal**: Stop bleeding trust and SEO juice.

- [ ] **MUST**: Fix Insurance 404 (update nav or create redirect)
- [ ] **MUST**: Consolidate H1/DOM — either PBHS ticket or JavaScript injection to rewrite H1 for accessibility
- [ ] **MUST**: 301 redirect 15 worst thin pages to parent pages (start with location spam duplicates)
- [ ] **MUST**: Purge all visible stock photos via CSS (`img[src*="photo609"] {display:none !important}` etc.)
- [ ] **MUST**: Implement sticky mobile CTA bar (Call/Text/Book)
- [ ] **SHOULD**: Merge "New Patient" pages (First Visit + Prep Guide + New Patient Info → single /new-patients/)
- [ ] **SHOULD**: Create "Wichita Community" pillar page to replace 3 location spam pages
- [ ] **SHOULD**: Add real insurance logos to footer

### Phase 2: Content & Photography (Days 31–60)
**Goal**: Authenticity upgrade.

- [ ] **MUST**: Professional photo shoot (Dr. Reno, team, office, 5 patients with releases)
- [ ] **MUST**: Replace all CSS-hidden stock images with real photos (upload to PBHS media library, update references)
- [ ] **MUST**: Consolidate remaining thin service pages into 6 category pillars
- [ ] **SHOULD**: Produce Dr. Reno welcome video (smartphone quality acceptable if authentic)
- [ ] **SHOULD**: Rewrite Services hub page with Dr. Reno's voice (not manufacturer copy)
- [ ] **SHOULD**: Implement before/after gallery with proper consent documentation
- [ ] **NICE**: First blog post: "Why We Invested in AI Dental Radiography for Wichita Families"

### Phase 3: Conversion Optimization (Days 61–90)
**Goal**: Turn visitors into appointments.

- [ ] **MUST**: Implement multi-step contact form (or upgrade to PBHS premium forms)
- [ ] **MUST**: Create specific landing pages for high-value services (Implants, Sedation) with unique CTAs
- [ ] **MUST**: Add Google Reviews widget to homepage and /reviews/
- [ ] **SHOULD**: A/B test headline: "Modern Family Dentistry" vs. "Wichita's Most Comfortable Dental Experience"
- [ ] **SHOULD**: Implement "Schedule This Specific Service" buttons on service pages
- [ ] **NICE**: Launch membership plan calculator (interactive: "See your savings")

### Phase 4: Market Dominance (Days 91–180)
**Goal**: Best in Wichita, period.

- [ ] **MUST**: Complete migration off PBHS if platform limits persist, OR confirm PBHS can support remaining requirements
- [ ] **MUST**: Launch video testimonial campaign (3 new videos/month)
- [ ] **MUST**: Implement live chat ( staffed during office hours)
- [ ] **SHOULD**: Create "Dental Anxiety" specific funnel (landing page + sedation info + soft CTA)
- [ ] **SHOULD**: Optimize for Core Web Vitals (sub-2.5s LCP)
- [ ] **NICE**: Implement "Refer a Friend" digital program with tracking
- [ ] **NICE**: Create Spanish-language version of /new-patients/ (Wichita demographic consideration)

## 14. Validation Gates + Risks

**Go/No-Go Gates**:
1. **Day 15**: PBHS responds to layoutAccess ticket? **If NO**: Accelerate platform migration planning
2. **Day 30**: Photo shoot completed with 20+ usable images? **If NO**: Delay Phase 2, use temporary local Wichita stock (university, landmarks) rather than fake dental stock
3. **Day 60**: Page count reduced from 93 to <30? **If NO**: Risk of continued SEO cannibalization; prioritize technical consolidation over content creation
4. **Day 90**: Conversion rate (form fills + calls) increased 25%? **If NO**: Revisit CTA placement and headline messaging

**Risks & Mitigations**:
- **PBHS Lock-in**: Template2120 may not support true customization. **Mitigation**: Use CSS overrides as bridge; budget $15–25k for platform migration if needed
- **Doctor Availability**: Dr. Reno too busy for photo/video shoot. **Mitigation**: Schedule 2-hour block on slow Thursday; use iPhone cinematic mode if pro crew unavailable
- **Patient Photo Releases**: Fear of HIPAA/compliance. **Mitigation**: Use staff as models for hero images; use abstract clinical shots (hands only) for procedure pages until patient releases secured
- **SEO Traffic Dip**: Consolidating 93 pages may temporarily drop rankings. **Mitigation**: 301 redirects pass equity; expected 6-week dip followed by 3-month growth as authority consolidates

**Success Metrics**:
- **Bounce Rate**: <40% (currently likely 60%+ due to template confusion)
- **Time on Site**: >3:00 minutes (indicates content engagement)
- **New Patient Conversion**: >5% of visitors schedule (industry avg 2–3%)
- **Page Load**: <2.0 seconds mobile
- **Organic Rankings**: Position 1–3 for "Wichita family dentist," "dentist near me," "dental implants Wichita"

---
**Final Note**: You have already proven the site can improve rapidly with the 2026-07-10 CSS overrides. The path to "best ever" requires the courage to delete 80% of your current pages and invest in real photography. Dr. Reno has the practice; the website just needs to match his quality.