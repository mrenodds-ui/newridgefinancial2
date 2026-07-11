# PBHS Ticket — Best-Ever Website Follow-up (New Ridge / renodentalcare.org)

**Subject:** Layout access, H1 source edit, 301 redirects, custom CSS/JS bundle — New Ridge Family Dental

Hi PBHS team,

We’re executing a professional redesign on https://www.renodentalcare.org/ and need platform support so we can finish cleanly (without page-content CSS workarounds on every page).

## Please enable / complete

1. **Layout editing for our admin login**  
   Current flags: `layoutAccess: false`, `canUpdateLayouts: false`. Layout panels stay blank. Need access to edit Layout parts (Banner: Two Columns, Fluid Media / Meet the Doctor, featured icon tiles).

2. **Source H1 / hero copy on homepage**  
   Layout still outputs H1 “Comfort-Focused Dentistry for Wichita Families”. We need the **actual DOM H1** (and subhead) set to:  
   - H1: **Modern Family Dentistry in Wichita**  
   - Subhead: **Comprehensive dental care for every generation. Dr. Michael Reno combines advanced technology with uncompromising comfort.**

3. **Official custom CSS/JS bundle update**  
   Live site uses `#pbhs-custom-styles-css` + footer “WordPress PBHS CTA helper”. Please either grant edit access to that injection path **or** merge our approved overrides into the official bundle so we can remove temporary `<style id="nr-pro-sitewide">` duplicated on pages.

4. **301 redirects** (SEO consolidation)  
   Please implement 301s (or provide a method) for thin/duplicate pages into hubs, starting with:  
   - `/downtown-wichita-dentist/` → `/`  
   - `/dentist-in-northwest-wichita/` → `/`  
   - `/family-dentist-in-south-wichita/` → `/`  
   - `/covid-19/` → `/`  
   - `/admin2/` → remove from public / noindex  
   Full consolidation list (~93 → ~18) available on request.

5. **Remove template stock assets from homepage components**  
   Featured tiles still reference PBHS `rw-assets` stock photos and `demo-logo-2156-lg.png`. Please replace with our media library office/doctor photos or allow us to edit those layout image fields.

6. **Do not** switch themes or reset layouts without coordinating with us.

## Already completed on our side
- Color Options navy `#1E3A5F`
- Banner Slides office photo
- Mega-nav cleanup, hero single image, Meet the Doctor = Dr. Reno photo
- New Patient Experience hub, Insurance & Payment hub (`/insurance-and-payment/`)
- Sticky mobile Call/Book bar, review section cleanup
- Soft-redirect content on location spam pages; drafted `admin2` + `covid-19`

Thank you,  
Dr. Michael Reno / New Ridge Family Dental  
https://www.renodentalcare.org/admin
