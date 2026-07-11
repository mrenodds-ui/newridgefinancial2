# Moonshot AI — New Ridge Website Professional Redesign (CONSULT)

**Date:** 2026-07-10  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Site:** https://www.renodentalcare.org/  
**Platform:** PBHS WordPress (admin `/admin`)  
**Script:** `scripts/run_moonshot_website_pro_redesign_consult.py`  
**Apply:** DO NOT EDIT LIVE until operator approves + logs into WP admin.

## Operator request (verbatim)

> can you interact with revenuewell via ui to have moonshot ai look at my website and update it to highly professional website page?
my website is www.renodentalcare.org. i want both

---

# Verdict

## 0. Operator Intent + Platform Reality (PBHS/WordPress vs RevenueWell)

**Intent:** You requested a "highly professional" redesign via RevenueWell UI interaction.

**Reality Check:** Your site runs on **PBHS WordPress** (evidenced by "Family Dentistry Website Design by PBHS © 2026" footer and `/admin` → `wp-login.php`), **not** RevenueWell's drag-drop CMS. 

- **What you can edit now:** Content, menus, pages, images via WordPress Admin
- **What requires PBHS:** Theme structural changes, color palette adjustments, font changes, hero layout modifications
- **RevenueWell integration:** Likely only the patient portal/scheduling widget embedded in pages, not the site builder

**Path forward:** Proceed with professional redesign recommendations below; execute via WP Admin for content/IA changes, submit PBHS support tickets for structural/theme changes.

---

## 1. Critique of Current Site (why it feels less professional)

**MAJOR FRICTION POINTS:**

1. **Mega-link bar (30+ SEO links):** Creates visual spam and anxiety. Signals "old-school SEO manipulation" rather than confident healthcare brand.
2. **Ops-heavy homepage hierarchy:** "Financial Agreement Policy" as a top-3 destination suggests bureaucracy before care. New patients see paperwork before warmth.
3. **Dated hero collage:** The 4-panel photo grid (2015-2018 aesthetic) lacks the immersive, single-focus imagery expected of modern dental practices.
4. **Low-contrast CTAs:** Blue buttons with copper text fail WCAG contrast standards and look muddy.
5. **Confusing review labels:** "READ MORE REVIEWS ABOUT MISSED APPOINTMENT POLICY" accidentally highlights penalties rather than clinical excellence.
6. **CTA competition:** 5+ competing actions above the fold (Call, Request Appt, Portal, Financial Agreement, Registration) with no visual hierarchy.
7. **Visual density:** Lacks white space; elements bleed together without breathing room.

**WHAT WORKS (KEEP):**
- Strong office photography (clean, modern interior)
- Clear service categorization (Preventive/Restorative/Cosmetic/Urgent)
- Dr. Reno’s credentials and approachable positioning
- Accurate NAP (Name/Address/Phone) and consistent hours
- Accessibility widget (maintain compliance)
- Membership plan popup (valuable for uninsured patients)

---

## 2. Recommended Professional Design Direction (primary)

**Brand Position:** "Elevated Family Dentistry" — combining clinical precision with approachable warmth. The name "New Ridge" implies stability and elevation; the design should feel grounded yet modern.

**Typography:**
- **Primary:** Clean geometric sans-serif (Inter, Source Sans Pro, or system-ui)
- **Headings:** 40-48px hero, 600 weight, tight line-height (1.1)
- **Body:** 18px minimum, 1.6 line-height, #2D3748 (slate) not pure black
- **Eliminate:** Script fonts, all-caps body text, copper-colored links on blue

**Color System:**
- **Primary:** Deep navy (#1E3A5F) or charcoal — authority, medical trust
- **Accent:** Warm copper (#B87333) **only** as underline accents or icon fills, never as text on colored backgrounds
- **Background:** Warm white (#FAFAF9) rather than stark white — reduces clinical coldness
- **CTA Primary:** High-contrast navy or teal button with white text
- **CTA Secondary:** Ghost/outline button for phone

**Hero Strategy:**
- **Single full-width image** (not collage): Modern operatory or welcoming reception with natural light
- **Left-aligned text block** over subtle gradient overlay (20% dark)
- **Maximum two CTAs:** Primary "Request Appointment" (filled), Secondary "Call (316) 722-6060" (outline)
- **No scrolling text, no autoplay video**

**Density & Hierarchy:**
- **Whitespace:** 80-100px vertical padding between sections
- **Card-based organization:** Services as 4 clean tiles, not lists
- **Z-pattern reading:** Logo/nav → Hero value prop → Trust indicators → Action

---

## 3. Homepage Wireframe (text) — first viewport + below-fold

### VIEWPORT 1: Hero Section (Above Fold)
```
[ALERT BAR - subtle gray] 
Monday–Thursday, 7:00 AM–4:00 PM | Now welcoming new patients

[NAVIGATION - sticky on scroll]
LOGO: New Ridge Family Dental          Services ▼ | New Patients | Our Practice | Contact
                                        [Request Appointment]  (316) 722-6060

[HERO - Full width, single image: Modern operatory or team photo]
H1: Modern Family Dentistry in Wichita
Subhead: Comprehensive, comfortable care for every age. Dr. Michael Reno and our 
         team serve Wichita, Andover, Goddard, and surrounding communities 
         with advanced technology and genuine hospitality.

[CTA Group]
[Request Appointment]  [Call (316) 722-6060]
↓
[Trust micro-bar: 5-star icon] "Patient-centered care since [VERIFY YEAR]"
```

### BELOW FOLD SECTIONS

**Section 2: Services (4-Card Grid)**
```
Comprehensive Care Under One Roof

[Card 1: Icon] Preventive Dentistry
     Cleanings, exams, and early intervention for healthy smiles.

[Card 2: Icon] Restorative Solutions  
     Crowns, bridges, and fillings that look and feel natural.

[Card 3: Icon] Cosmetic Enhancement
     Whitening, veneers, and smile design.

[Card 4: Icon] Urgent & Comfort Care
     Same-day emergency appointments and sedation options.

[View All Services]
```

**Section 3: New Patient Pathway**
```
Your First Visit, Simplified

1. Book Online or Call
   Schedule your appointment in under 2 minutes.

2. Complete Forms
   Save time with digital registration sent to your phone.

3. Meet Your Team
   Comprehensive exam, digital X-rays, and personalized treatment plan.

[New Patient Information] [Request Appointment]
```

**Section 4: Dr. Reno Introduction**
```
Meet Dr. Michael Reno

[Photo: Professional headshot, white coat, warm background]

"Every patient deserves dentistry that respects their time, 
comfort, and long-term health."

Board-certified dentist serving Wichita families. Graduate of [VERIFY SCHOOL]. 
Committed to continuing education and conservative treatment approaches.

[Meet the Doctor] [Our Team]
```

**Section 5: Social Proof**
```
What Wichita Families Are Saying

[Clean carousel: Star rating + Quote + Name only]
"Dr. Reno made my daughter feel so comfortable for her first filling."
— Sarah M., Wichita

[Read More Reviews]
```

**Section 6: Location & Hours**
```
Visit New Ridge Family Dental

[Map embed]
2135 North Ridge Rd Ste 700
Wichita, KS 67212

Monday–Thursday: 7:00 AM – 4:00 PM
Friday–Sunday: Closed

(316) 722-6060

[Get Directions]
```

---

## 4. Information Architecture — Nav Cleanup

**REMOVE/MERGE:**
- **DELETE:** Mega-link bar entirely (30+ utility links)
- **DELETE:** "Financial Agreement Policy" from primary navigation (move to footer/legal or New Patients sub-page)
- **DELETE:** "Missed Appointment Policy" from review carousel labels
- **MERGE:** "About" + "Meet the Doctor" → "Our Practice" (dropdown: About Dr. Reno, Our Team, Office Tour)

**NEW PRIMARY NAV:**
```
Home | Services ▼ | New Patients | Our Practice ▼ | Contact

Services Dropdown:
- Preventive Dentistry
- Restorative Dentistry  
- Cosmetic Dentistry
- Urgent & Emergency Care
- View All Services

New Patients (Landing page):
- First Visit Expectations
- Patient Forms (Portal link)
- Financial Information
- Insurance & Payment

Our Practice Dropdown:
- About Dr. Reno
- Meet the Team
- Office Tour / Technology
- Community Involvement

Contact:
- Location & Hours
- Request Appointment
- Patient Portal (outbound link)
```

**FOOTER:**
```
[Left Column]
New Ridge Family Dental
2135 North Ridge Rd Ste 700
Wichita, KS 67212
(316) 722-6060

[Middle Column]
Hours:
Monday–Thursday: 7AM–4PM
Friday–Sunday: Closed

[Right Column]
Quick Links:
Request Appointment | Patient Portal | Privacy Policy | Accessibility Statement

[Bottom Bar]
© 2026 New Ridge Family Dental. Website by PBHS.
```

---

## 5. Copy Spec (CONSULT) — hero, CTAs, section headlines

**HERO COPY (Paste-ready):**
```
H1: Modern Family Dentistry in Wichita

Subhead: Comprehensive dental care for every generation. 
Dr. Michael Reno combines advanced technology with 
uncompromising comfort to serve Wichita, Andover, 
Goddard, and surrounding communities.

CTA Primary: Request Appointment
CTA Secondary: Call (316) 722-6060
```

**SECTION HEADLINES:**
- "Comprehensive Care Under One Roof" (Services)
- "Your First Visit, Simplified" (New Patient onboarding)
- "Meet Dr. Michael Reno" (Bio)
- "What Wichita Families Are Saying" (Reviews)
- "Investing in Your Smile" (Financing/Insurance)

**MICROCOPY FIXES:**
- Change: "Financial Agreement Policy" → "Payment Options"
- Change: "OPEN PATIENT PORTAL" → "Patient Login"
- Change: "AI Radiographs" (if keeping) → "Advanced Digital Imaging"

**IMPORTANT:** Verify Dr. Reno's specific dental school and any actual awards/affiliations before adding credentials beyond "DDS."

---

## 6. Page-by-Page Priority List

**PHASE 1: Homepage (Conversion Critical)**
- MUST: Remove mega-link bar
- MUST: Simplify hero to single image + two CTAs
- MUST: Remove "Financial Agreement" from icon strip
- SHOULD: Reorganize services as 4-card grid
- SHOULD: Clean review carousel (remove policy labels)

**PHASE 2: New Patients (Conversion Page)**
- MUST: Create clear "First Visit" pathway (Step 1, 2, 3)
- MUST: Embed Patient Portal login prominently but not dominantly
- SHOULD: Add video tour of office (if available)

**PHASE 3: Services (SEO & Education)**
- NICE: Add before/after gallery (only with actual patient consent)
- NICE: Expand service descriptions with FAQ schema

**PHASE 4: Contact/Location**
- MUST: Verify Google Maps embed accuracy
- MUST: Click-to-call mobile optimization
- SHOULD: Add "Text Us" option if practice supports SMS

---

## 7. RevenueWell / PBHS Edit Feasibility

**YOU CAN DO NOW (WordPress Admin):**
- Edit page content, headlines, button text
- Reorganize menus (Appearance > Menus)
- Remove widgets (mega-link bar likely a widget or header element)
- Update footer text
- Replace images (Media Library)
- Toggle page sections on/off (if PBHS theme has visibility toggles)

**REQUIRES PBHS SUPPORT TICKET:**
- Changing hero layout from 4-panel to single image
- Adjusting color palette (blue/copper contrast fixes)
- Font family changes
- Custom CSS implementation
- Adding new page templates
- Schema markup modifications

**REQUIRES REVENUEWELL (if integrated):**
- Modifying the "Request Appointment" widget styling
- Membership plan popup content (likely RevenueWell feature)

**RECOMMENDED WORKFLOW:**
1. Log into WP Admin (`/admin`)
2. Navigate to Pages > Home
3. Look for PBHS Page Builder or similar meta boxes
4. If locked layout: Document desired changes, submit PBHS ticket referencing "Professional redesign—hero layout change, color contrast fix"

---

## 8. Phases + Validation Gate

**PHASE 1: Foundation (Week 1-2) — CONSULT APPROVAL REQUIRED**
- [ ] Remove mega-link bar
- [ ] Update homepage headline/subhead copy
- [ ] Reorganize navigation (simplify to 5 items)
- [ ] Remove "Financial Agreement" from homepage icon strip
- [ ] Fix review carousel labels (remove policy references)

**VALIDATION GATE:** Review staging site (if available) or screenshot mockups. Approve information architecture before visual changes.

**PHASE 2: Visual Professionalization (Week 3-4) — PBHS INVOLVEMENT**
- [ ] Submit PBHS ticket: Hero layout change (single image)
- [ ] Submit PBHS ticket: Color contrast fix (CTA buttons)
- [ ] Replace hero image with high-res single photograph
- [ ] Implement new card-based service grid

**VALIDATION GATE:** Mobile responsiveness check—ensure new hero/buttons work on iPhone/Android.

**PHASE 3: Conversion Optimization (Week 5-6)**
- [ ] Rewrite New Patients page with clear pathway
- [ ] Optimize Contact page for local SEO
- [ ] Add structured data (LocalBusiness schema) if not present

**POST-LAUNCH:**
- [ ] Monitor page speed (GTmetrix)
- [ ] Check appointment request conversion rate (compare to baseline)
- [ ] A/B test headline variations

---

## 9. Risks & Rollback

**RISKS:**

1. **SEO Disruption from Mega-Link Removal**
   - *Risk:* Those 30+ links may be passing authority to interior pages
   - *Mitigation:* Ensure proper internal linking within new Services dropdown and footer sitemap
   - *Rollback:* Re-enable mega-bar if organic traffic drops >15% within 30 days

2. **PBHS Platform Limitations**
   - *Risk:* Theme may not support single-image hero without custom development fees ($500-$2000)
   - *Mitigation:* Request quote upfront; consider keeping current hero but improving copy/overlay if cost prohibitive

3. **Color Contrast Compliance**
   - *Risk:* Current blue/copper fails WCAG AA standards (legal risk for ADA)
   - *Mitigation:* Must fix via PBHS or custom CSS; do not leave as-is

4. **Content Freeze During PBHS Updates**
   - *Risk:* PBHS updates may take 5-7 business days; site looks inconsistent during transition
   - *Mitigation:* Schedule changes during low-traffic periods (Thursday PM/Friday AM)

**ROLLBACK PLAN:**
- WordPress revisions store previous page versions (30-day history)
- PBHS themes usually allow "Revert to Default" for specific sections
- Document current widget configuration (screenshots) before removing mega-link bar

---

**NEXT STEP:** Approve this consult plan. Once approved, proceed to Phase 1 edits via WordPress Admin, or request PBHS quote for structural hero changes. Do not proceed with visual edits until information architecture (navigation) is approved.