# Sensei Public Web Scope Research

## Purpose

This memo summarizes public web research on whether Sensei's published product scope goes beyond a narrow Patient Manager workflow.

## Short Answer

Yes. Public Sensei web materials describe Patient Manager as one feature within a broader Sensei Cloud platform, not as the whole product.

The public site separates Sensei into broader categories such as:

- Patient Engagement
- Patient Care
- Business Health
- Sensei Cloud Apps
- enterprise or DSO workflows

That supports the conclusion that the observed local integration surface could belong to a broader Sensei platform footprint, not only Patient Manager.

## Public Sources Reviewed

### Sensei home page

Source: [Sensei home page](https://gosensei.com/)

Relevant public statements:

- Sensei Cloud is described as a connected, end-to-end platform.
- The site says dentists can handle everything from patient care to practice management with one platform.
- It separates solutions into Patient Engagement, Patient Care, and Business Health.
- It says the product provides real-time visibility into operational, clinical, and financial performance.

Why it matters:

This is broader than a standalone Patient Manager product. It supports practice management, analytics, clinical, operational, and financial workflows.

### Patient Engagement page

Source: [Patient Engagement page](https://gosensei.com/integrated-tools/patient-engagement/)

Relevant public statements:

- Patient Manager is listed under Patient Engagement.
- Patient Manager is described around appointment management, no-show reduction, two-way communication, unified messaging, online scheduling, digital forms, reputation management, recalls, and reminders.

Why it matters:

This defines the narrower Patient Manager lane: communication, scheduling, reminders, forms, and patient engagement.

### Patient Manager page

Source: [Patient Manager page](https://gosensei.com/integrated-tools-patient-engagement-patient-manager/)

Relevant public statements:

- Patient Manager is described as attracting, scheduling, and retaining patients through automated communication tools.
- The page emphasizes online booking, recalls, follow-ups, unfinished treatment plans, reminders, digital check-in, marketing campaigns, and patient reviews.

Why it matters:

This supports patient and appointment data use. It does not clearly explain transaction capability, broad insurance handling, `Pnotes`, or broader provider/location/reference entity scope by itself.

### Business Health page

Source: [Business Health page](https://gosensei.com/integrated-tools/business-health/)

Relevant public statements:

- Business Health includes automated billing and insurance processing.
- It lists Payment Manager, Insights Manager, eClaims, and eVerifications.
- Payment Manager posts payments automatically into the patient ledger.
- Insights Manager provides business analytics.
- eClaims automates insurance claims.
- eVerifications provides real-time insurance verification.

Why it matters:

This directly shows that Sensei's public product scope includes billing, insurance, analytics, payment, and ledger workflows outside narrow Patient Manager.

### Payment Manager page

Source: [Payment Manager page](https://gosensei.com/integrated-tools-business-health-payment-manager/)

Relevant public statements:

- Payment Manager is integrated payment processing.
- Payment data can be posted directly to the patient ledger.
- The page describes secure transaction logging, recurring payments, stored cards, and automated payment tools.

Why it matters:

This explains why transaction, ledger, payment, and writeback-style behavior may exist in the broader platform. It is not Patient Manager alone.

### Insights Manager page

Source: [Insights Manager page](https://gosensei.com/integrated-tools-business-health-insights-manager/)

Relevant public statements:

- Insights Manager is a practice reporting and analytics tool.
- It provides performance data, analytics, customizable dashboards, consolidated data across practices, operational efficiency, and profitability support.

Why it matters:

This explains why broader operational, clinical, financial, provider, location, and reference data may be used by the broader Sensei platform.

### Patient Care page

Source: [Patient Care page](https://gosensei.com/integrated-tools/patient-care/)

Relevant public statements:

- Patient Care tools include Rx Manager and Imaging.
- Rx Manager works with patient information and prescribing workflows.
- Imaging connects diagnostic images and patient records.

Why it matters:

This is also outside Patient Manager and supports a broader clinical data surface.

### Sensei Cloud Apps page

Source: [Sensei Cloud Apps page](https://gosensei.com/cloud-apps)

Relevant public statements:

- Sensei Cloud Apps describes schedule access, patient details, morning huddles, patient flags, outstanding balances, insurance verification, and call handling.
- Eligibility IQ automatically checks patient insurance before appointments and pulls benefit details from the PMS system.

Why it matters:

This publicly supports a broader integration model involving schedule, patient details, balances, insurance eligibility, notes or flags, and PMS-sourced benefit details.

### Sensei Cloud Patient Bridge help article

Source: [Sensei Cloud Patient Bridge help article](https://help.gosensei.com/hc/en-us/articles/22100846565783-Sensei-Cloud-Patient-Bridge)

Relevant public statements:

- Patient Bridge supports SMS messages, recalls, reminders, reviews, online booking, treatment plans, and payment-status checks.

Why it matters:

Even patient-engagement tooling can include treatment plan and payment-status workflows, but the help article still does not by itself justify every broader local entity observed.

### QuickBooks Online integration help article

Source: [QuickBooks Online integration help article](https://help.gosensei.com/hc/en-us/articles/24578354962839-How-to-Set-Up-and-Use-QuickBooks-Online-Integration)

Relevant public statements:

- Sensei Cloud transaction records can be exported to QuickBooks Online.
- The article references payment types including cash, check, credit card, debit card, insurance payments, and refund payments.
- It describes exporting transaction records from the Financial Daysheet.

Why it matters:

This is strong public evidence that Sensei supports transaction and financial data workflows outside Patient Manager.

### DentalXChange payer enrollment help article

Source: [DentalXChange payer enrollment help article](https://help.gosensei.com/hc/en-us/articles/22892993387159-Enrollment-for-Payers-with-DentalXChange)

Relevant public statements:

- The help article covers payer enrollment and requires office and provider information.
- Related articles include medical billing and claim-related workflows.

Why it matters:

This supports insurance/payer/provider workflows outside a narrow Patient Manager explanation.

## Web Research Conclusion

The public web materials support this distinction:

Patient Manager itself appears focused mainly on patient engagement, communication, scheduling, reminders, recalls, online booking, forms, check-in, marketing, reviews, follow-ups, and treatment-plan outreach.

The broader Sensei platform publicly includes additional modules for:

- payments
- ledgers
- transactions
- business analytics
- insurance claims
- insurance verification
- prescribing
- imaging
- schedule access
- patient flags
- outstanding balances
- cloud apps
- enterprise centralized workflows

Therefore, if the local machine shows insurance, transaction, notes, provider, location, reference, payment, ledger, analytics, or writeback-related behavior, public Sensei materials suggest that behavior is more consistent with the broader Sensei Cloud platform than with Patient Manager alone.

## Practical Interpretation For This Machine

The local evidence showed behavior beyond a narrow Patient Manager expectation, including:

- insurance or responsible-party handling
- provider, location, ADA, and reference entity scope
- `Pnotes` capability
- `Transaction` capability
- inbound import and writeback surfaces

Public web materials show that Sensei does offer broader product areas that could explain some of that behavior. But that does not prove the practice licensed, enabled, approved, or contractually authorized every broader module.

## Question To Send The Vendor

Based on public web materials and local evidence, ask the vendor:

Is this installation limited to Patient Manager, or is it operating as part of the broader Sensei Cloud platform, including Business Health, Payment Manager, Insights Manager, eClaims, eVerifications, Cloud Apps, or other modules?
