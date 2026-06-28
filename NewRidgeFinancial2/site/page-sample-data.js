/**
 * Sample / demo data for program pages — matches PNG mockups.
 * Clearly labeled in UI; not connected to live sources.
 */
const PageSampleData = (function () {
  const financial = {
    dateRange: "May 1 – May 31, 2025",
    compareRange: "vs. Apr 1 – Apr 30, 2025",
    kpis: [
      { label: "Production MTD", value: "$1,234,567", tone: "gold", trend: "+12.4%", trendDir: "up", sub: "May 1 – May 31" },
      { label: "Collections MTD", value: "$987,654", tone: "green", trend: "+10.3%", trendDir: "up", sub: "Collection rate 80.1% ↑ 2.1pp" },
      { label: "Net A/R", value: "$1,456,789", tone: "blue", trend: "-5.2%", trendDir: "down", sub: "Days in A/R 42 ↓ -3" },
      { label: "EBITDA MTD", value: "$456,789", tone: "purple", trend: "+15.7%", trendDir: "up", sub: "EBITDA margin 37.0% ↑ 1.0pp" },
    ],
    productionTrend: {
      labels: ["Jun '24", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan '25", "Feb", "Mar", "Apr", "May"],
      production: [920, 940, 955, 980, 1010, 1040, 1080, 1100, 1120, 1150, 1180, 1234],
      average: [900, 905, 910, 915, 920, 925, 930, 935, 940, 945, 950, 955],
      ytd: [
        { label: "YTD Production", value: "$5,678,901" },
        { label: "YTD Collections", value: "$4,567,890" },
        { label: "YTD Collection Rate", value: "80.4%" },
      ],
    },
    payerMix: {
      total: "$987,654",
      slices: [
        { label: "Delta Dental", pct: 28, amount: "$276,543", color: "#d6b15e" },
        { label: "Cigna", pct: 22, amount: "$217,284", color: "#7dd3fc" },
        { label: "MetLife", pct: 18, amount: "$177,778", color: "#78a86b" },
        { label: "Aetna", pct: 15, amount: "$148,148", color: "#a78bfa" },
        { label: "Other", pct: 17, amount: "$167,901", color: "#64748b" },
      ],
      footer: "Insurance collection rate 85.2% ↑ 2.3pp",
    },
    providers: [
      { name: "Dr. Smith", amount: "$312,456", pct: 25 },
      { name: "Dr. Johnson", amount: "$271,234", pct: 22 },
      { name: "Dr. Williams", amount: "$234,567", pct: 19 },
      { name: "Dr. Brown", amount: "$198,765", pct: 16 },
      { name: "Dr. Davis", amount: "$217,545", pct: 18 },
    ],
    freshness: [
      { system: "Practice Management", status: "Synced", time: "12:15 AM", freq: "Daily" },
      { system: "EHR", status: "Synced", time: "12:10 AM", freq: "Daily" },
      { system: "Payers / ERA", status: "Delay", time: "11:45 PM", freq: "Daily" },
      { system: "QuickBooks", status: "Synced", time: "8:42 AM", freq: "Hourly" },
      { system: "Bank Feed", status: "Synced", time: "6:00 AM", freq: "Daily" },
      { system: "Document Index", status: "Synced", time: "12:05 AM", freq: "Daily" },
    ],
    quality: { score: 96, categories: [
      { label: "Completeness", score: 98 },
      { label: "Accuracy", score: 95 },
      { label: "Timeliness", score: 94 },
      { label: "Consistency", score: 97 },
    ]},
    footer: { disclaimer: "All data is preliminary and unaudited.", refreshed: "May 31, 2025 12:30 AM" },
  };

  const softdent = {
    date: "May 22, 2025",
    status: "Connected",
    hero: { label: "DAYSHEET A/R", value: "$318,541.27", trend: "7.6% vs May 15, 2025", trendDir: "up" },
    subMetrics: [
      { label: "Unbilled", value: "$47,812.09" },
      { label: "Current", value: "$162,719.48" },
      { label: "> 30 Days", value: "$78,342.11" },
      { label: "> 90 Days", value: "$29,667.59" },
    ],
    aging: [
      { bucket: "0-30 Days", amount: "$162,719.48", pct: 51.1 },
      { bucket: "31-60 Days", amount: "$48,622.63", pct: 15.3 },
      { bucket: "61-90 Days", amount: "$29,719.48", pct: 9.3 },
      { bucket: "91-120 Days", amount: "$18,622.63", pct: 5.8 },
      { bucket: ">120 Days", amount: "$58,857.05", pct: 18.5 },
    ],
    responsibility: {
      total: "$318,541.27",
      insurance: { amount: "$207,845.31", pct: 65.2 },
      patient: { amount: "$110,695.96", pct: 34.8 },
      collectability: "85.7%",
      collectable: "$94,867.50",
    },
    health: [
      { label: "Connection", value: "Healthy", ok: true },
      { label: "Data Freshness", value: "23 min ago", ok: true },
      { label: "Daysheet Load", value: "Completed", ok: true },
      { label: "Last Successful Export", value: "23 min ago", ok: true },
      { label: "Next Scheduled Export", value: "In 37 min", ok: true },
    ],
    glance: [
      { label: "Total Patients", value: "5,642" },
      { label: "Active Patients", value: "2,341" },
      { label: "New Patients MTD", value: "126" },
      { label: "Total Procedures MTD", value: "1,987" },
      { label: "Production MTD", value: "$436,982.11" },
      { label: "Collections MTD", value: "$398,114.23" },
    ],
    exports: [
      { name: "Daysheet Export", source: "SoftDent", dataset: "A/R Daysheet", status: "SUCCESS", completed: "May 22, 2025 11:37 AM", records: "1,247", size: "842 KB" },
      { name: "Patient Export", source: "SoftDent", dataset: "Patient Demographics", status: "SUCCESS", completed: "May 22, 2025 11:37 AM", records: "5,642", size: "1.2 MB" },
      { name: "Transactions Export", source: "SoftDent", dataset: "Transactions", status: "SUCCESS", completed: "May 22, 2025 11:36 AM", records: "3,891", size: "956 KB" },
      { name: "Procedures Export", source: "SoftDent", dataset: "Procedures", status: "SUCCESS", completed: "May 22, 2025 11:36 AM", records: "1,987", size: "624 KB" },
    ],
  };

  const quickbooks = {
    syncStatus: "Connected",
    lastSync: "May 19, 2025 8:42 AM CDT",
    pl: {
      range: "Jan 1 – May 19, 2025",
      rows: [
        { category: "Revenue", amount: "$2,182,742", change: "▲ 18.6%", changeTone: "up" },
        { category: "Cost of Goods Sold", amount: "$620,843", change: "▲ 7.4%", changeTone: "down" },
        { category: "Gross Profit", amount: "$1,561,899", change: "▲ 23.2%", changeTone: "up", sub: "71.6% Margin" },
        { category: "Operating Expenses", amount: "$985,103", change: "▲ 5.1%", changeTone: "down" },
        { category: "Other Income", amount: "$13,750", change: "▲ 42.8%", changeTone: "up" },
        { category: "Other Expenses", amount: "$4,215", change: "▼ 12.3%", changeTone: "up" },
        { category: "Net Income", amount: "$586,331", change: "▲ 36.7%", changeTone: "up", sub: "26.9% Margin", highlight: true },
      ],
    },
    monthlyExpenses: {
      labels: ["Jun '24", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May"],
      values: [82000, 88000, 91000, 94000, 98000, 102000, 108000, 105000, 99000, 101000, 98000, 95000],
    },
    expenseCategories: {
      total: "$985,103",
      slices: [
        { label: "Payroll & Benefits", amount: "$412,783", pct: 41.9, color: "#7dd3fc" },
        { label: "Professional Services", amount: "$178,452", pct: 18.1, color: "#f59e0b" },
        { label: "Sales & Marketing", amount: "$132,108", pct: 13.4, color: "#6366f1" },
        { label: "Rent & Facilities", amount: "$98,331", pct: 10.0, color: "#64748b" },
        { label: "Software & Subscriptions", amount: "$62,771", pct: 6.4, color: "#38bdf8" },
        { label: "Travel & Entertainment", amount: "$38,912", pct: 4.0, color: "#a16207" },
        { label: "Other", amount: "$62,746", pct: 6.4, color: "#94a3b8" },
      ],
    },
    ebitdaCandidates: [
      { desc: "Owner Discretionary Expenses", amount: "$42,500", type: "Discretionary", typeTone: "warn" },
      { desc: "One-Time Legal Fees", amount: "$28,750", type: "One-Time", typeTone: "info" },
      { desc: "Non-Recurring Consulting", amount: "$15,925", type: "One-Time", typeTone: "info" },
      { desc: "Personal Vehicle Expenses", amount: "$9,000", type: "Discretionary", typeTone: "warn" },
    ],
    ebitdaTotal: "$96,175",
    sync: {
      connection: "QuickBooks Online",
      access: "Read-Only",
      frequency: "Every 60 Minutes",
      lastSync: "May 19, 2025 8:42 AM CDT",
      status: "Connected",
    },
  };

  const ar = {
    dateRange: "May 18 – Jun 17, 2025",
    kpis: [
      { label: "Total Outstanding", value: "$2,842,651.18", tone: "gold" },
      { label: "vs. Prior 30 Days", value: "↓ 3.7%", tone: "green" },
      { label: "90+ Days %", value: "29.6%", tone: "muted" },
      { label: "Est. Uncollectible", value: "$143,987.32", tone: "muted" },
      { label: "Collections This 30 Days", value: "$317,842.11", tone: "green" },
    ],
    aging: [
      { label: "0-30 Days", amount: "$842,651.18", pct: 29.6, active: false },
      { label: "31-60 Days", amount: "$568,530.24", pct: 20.0, active: false },
      { label: "61-90 Days", amount: "$596,956.75", pct: 21.0, active: false },
      { label: "90+ Days", amount: "$834,513.01", pct: 29.4, active: true },
    ],
    collectionsTrend: {
      labels: ["May 18", "May 22", "May 26", "May 30", "Jun 3", "Jun 7", "Jun 11", "Jun 15"],
      current: [42000, 38000, 45000, 52000, 48000, 55000, 51000, 58000],
      prior: [40000, 36000, 42000, 48000, 44000, 50000, 47000, 52000],
    },
    topClaims: [
      { claim: "CLM-2024-8891", patient: "Robert Chen", insurance: "Delta Dental PPO", dos: "01/15/2025", billed: "$8,450.00", outstanding: "$8,450.00", days: 125 },
      { claim: "CLM-2024-8756", patient: "Maria Garcia", insurance: "Cigna Dental", dos: "01/02/2025", billed: "$6,200.00", outstanding: "$6,200.00", days: 139 },
      { claim: "CLM-2024-8623", patient: "James Wilson", insurance: "MetLife", dos: "01/08/2025", billed: "$5,875.00", outstanding: "$5,875.00", days: 133 },
      { claim: "CLM-2024-8490", patient: "Lisa Thompson", insurance: "Aetna", dos: "12/26/2024", billed: "$4,950.00", outstanding: "$4,950.00", days: 146 },
      { claim: "CLM-2024-8357", patient: "David Martinez", insurance: "Guardian", dos: "12/20/2024", billed: "$4,625.00", outstanding: "$4,625.00", days: 152 },
    ],
    followUp: [
      { status: "Ready", tone: "ok", count: 28, items: [{ label: "Verify insurance benefits", count: 8 }, { label: "Send patient statement", count: 12 }] },
      { status: "Needs Review", tone: "warn", count: 14, items: [{ label: "Insurance response received", count: 7 }, { label: "Partial payment posted", count: 4 }] },
      { status: "Blocked", tone: "red", count: 6, items: [{ label: "Waiting on patient response", count: 4 }, { label: "Missing documentation", count: 2 }] },
    ],
  };

  const claims = {
    safety: "Read-Only Mode",
    kpis: [
      { label: "Total Claims", value: "1,284", trend: "↑ 8.4% vs last 7 days" },
      { label: "Claim Readiness", value: "78%", trend: "↑ 6% vs last 7 days" },
      { label: "Avg Days in Workflow", value: "3.6", trend: "↓ 0.8 vs last 7 days" },
      { label: "Total Billed (7D)", value: "$312,650", trend: "↑ 12.7% vs last 7 days" },
      { label: "Est. Collection", value: "$187,230", trend: "72% of billed" },
    ],
    lanes: {
      Draft: {
        count: 142,
        cards: [
          { id: "CLM-0009947", patient: "John Smith", dob: "03/12/1985", procedure: "D8080", amount: "$4,850.00", age: "2d ago" },
          { id: "CLM-0009942", patient: "Emily Davis", dob: "07/22/1990", procedure: "D2740", amount: "$1,250.00", age: "3d ago" },
        ],
        more: 140,
      },
      "Needs Review": {
        count: 286,
        cards: [
          { id: "CLM-0009921", patient: "Michael Brown", dob: "11/05/1978", procedure: "D7210", amount: "$875.00", tag: "Missing Info", tagTone: "warn" },
          { id: "CLM-0009915", patient: "Sarah Wilson", dob: "02/18/1992", procedure: "D8080", amount: "$5,200.00", tag: "Missing Attachment", tagTone: "warn" },
        ],
        more: 284,
      },
      Ready: {
        count: 612,
        cards: [
          { id: "CLM-0009712", patient: "Sophia Wilson", dob: "09/14/2008", procedure: "D8080", amount: "$4,150.00", tag: "Ready", tagTone: "ok", selected: true },
          { id: "CLM-0009708", patient: "James Taylor", dob: "04/30/1987", procedure: "D2740", amount: "$1,180.00", tag: "Ready", tagTone: "ok" },
        ],
        more: 610,
      },
      Denied: {
        count: 244,
        cards: [
          { id: "CLM-0009654", patient: "Lisa Anderson", dob: "08/21/1975", procedure: "D8080", amount: "$4,950.00", tag: "CO-97", tagTone: "red" },
          { id: "CLM-0009648", patient: "Robert Lee", dob: "12/03/1983", procedure: "D7210", amount: "$920.00", tag: "DME-01", tagTone: "red" },
        ],
        more: 242,
      },
    },
    readiness: { overall: "78%", slices: [
      { label: "Ready", pct: 47, color: "#78a86b" },
      { label: "Needs Review", pct: 22, color: "#d6b15e" },
      { label: "Draft", pct: 11, color: "#64748b" },
      { label: "Denied", pct: 19, color: "#f87171" },
    ]},
    detail: {
      id: "CLM-0009712",
      patient: "Sophia Wilson",
      dob: "09/14/2008",
      age: 16,
      insurance: "Delta Dental PPO",
      billed: "$4,150.00",
      dos: "05/14/2025",
      procedure: "Comprehensive Orthodontic Treatment",
      code: "D8080",
      provider: "Dr. Jane Doe",
      npi: "1234567890",
      validation: 93,
      alert: "Claim is ready but cannot be submitted due to current Safety Posture (Read-Only Mode).",
    },
  };

  const narratives = {
    patientBar: {
      patient: "Sarah Johnson",
      dob: "05/14/1986",
      claim: "CLM-2025-04123",
      insurance: "Delta Dental PPO",
      dos: "04/28/2025",
      procedure: "D2740 - Crown",
      status: "Draft",
    },
    composer: {
      tone: "Professional",
      length: "Standard",
      focus: "Medical Necessity",
      keyPoints: [
        "Tooth #30 has extensive decay extending into the dentin",
        "Previous restoration failed due to recurrent decay",
        "Patient reports sensitivity to hot and cold",
        "Restoration is non-restorable with direct filling",
      ],
      context: "",
    },
    draft: "Patient presents with extensive carious lesion on tooth #30 (mandibular right first molar). Clinical examination reveals decay extending into the dentin with compromised structural integrity. Previous amalgam restoration has failed due to recurrent decay and marginal breakdown. Patient reports sensitivity to thermal stimuli. Radiographic evaluation confirms the need for full coverage restoration. A porcelain fused to metal crown (D2740) is medically necessary to restore form, function, and prevent further deterioration.",
    history: [
      { version: "v4", latest: true, modified: "May 12, 2025 2:34 PM", points: 4, length: "Standard", focus: "Medical Necessity", by: "Alex Donovan" },
      { version: "v3", modified: "May 12, 2025 1:15 PM", points: 3, length: "Standard", focus: "Medical Necessity", by: "Alex Donovan" },
      { version: "v2", modified: "May 11, 2025 4:22 PM", points: 3, length: "Brief", focus: "Clinical Findings", by: "Alex Donovan" },
      { version: "v1", modified: "May 11, 2025 10:08 AM", points: 2, length: "Brief", focus: "Clinical Findings", by: "Alex Donovan" },
    ],
  };

  const documents = {
    entity: "Gold Tooth Holdings, LLC",
    queue: [
      { id: "DOC-2025-05891", type: "Vendor Invoice", vendor: "Summit Services LLC", date: "05/19/2025", amount: "$4,850.00", status: "Pending Review", statusTone: "warn", age: 2, selected: true },
      { id: "DOC-2025-05887", type: "Vendor Invoice", vendor: "Office Supplies Co", date: "05/18/2025", amount: "$342.18", status: "Ready to Post", statusTone: "ok", age: 3 },
      { id: "DOC-2025-05882", type: "Credit Memo", vendor: "Tech Solutions Inc", date: "05/17/2025", amount: "-$125.00", status: "Posted", statusTone: "info", age: 4 },
      { id: "DOC-2025-05879", type: "Vendor Invoice", vendor: "Cleaning Services LLC", date: "05/16/2025", amount: "$875.00", status: "Pending Review", statusTone: "warn", age: 5 },
      { id: "DOC-2025-05875", type: "Vendor Invoice", vendor: "Marketing Agency", date: "05/15/2025", amount: "$2,500.00", status: "Ready to Post", statusTone: "ok", age: 6 },
    ],
    preview: {
      vendor: "SUMMIT SERVICES",
      invoice: "INV-77541",
      date: "05/19/2025",
      total: "$4,850.00",
      file: "INV-77541_SummitServices_051925.pdf",
      pages: "1 of 2",
      uploaded: "05/19/2025 9:41 AM",
    },
    posting: [
      { label: "Pending Review", count: 3, amount: "$5,944.93", tone: "warn" },
      { label: "Ready to Post", count: 3, amount: "$3,525.59", tone: "ok" },
      { label: "Posted (This Period)", count: 12, amount: "$48,231.48", tone: "info" },
      { label: "Total Documents", count: 142, amount: "All Time", tone: "muted" },
    ],
    workload: { reviewed: 6, total: 25, pct: 24 },
    period: {
      label: "May 2025",
      range: "05/01/2025 - 05/31/2025",
      documents: 25,
      total: "$54,176.41",
      posted: "$48,231.48",
      pending: "$5,944.93",
      postedPct: 88.0,
      slices: [
        { label: "Posted", pct: 88.0, color: "#7dd3fc" },
        { label: "Pending", pct: 10.9, color: "#d6b15e" },
        { label: "Ready to Post", pct: 0.0, color: "#78a86b" },
        { label: "Other", pct: 0.0, color: "#64748b" },
      ],
      updated: "05/20/2025 8:15 AM",
    },
  };

  const library = {
    results: 2843,
    storage: { indexed: 2843, usedPct: 68, capacity: "4.0 TB" },
    filters: ["Document Type", "Classification", "Mission", "Tag", "Date Range"],
    categories: ["Policies", "Statements", "Claims", "Clinical", "Reports"],
    docs: [
      { title: "Operation Phoenix Briefing", type: "PDF", size: "4.2 MB", tags: ["Briefing", "Phoenix", "Confidential"], updated: "May 24, 2025", by: "Admin", selected: true, tone: "red" },
      { title: "Mission Protocols v2.4", type: "DOCX", size: "1.8 MB", tags: ["Protocol", "Operations"], updated: "May 23, 2025", by: "Admin", tone: "blue" },
      { title: "Q2 Financial Summary", type: "XLSX", size: "892 KB", tags: ["Finance", "Quarterly"], updated: "May 22, 2025", by: "CFO", tone: "green" },
      { title: "Compliance Training Deck", type: "PPTX", size: "12.4 MB", tags: ["Training", "Compliance"], updated: "May 21, 2025", by: "HR", tone: "orange" },
      { title: "Patient Privacy Policy", type: "PDF", size: "256 KB", tags: ["Policy", "HIPAA"], updated: "May 20, 2025", by: "Legal", tone: "red" },
      { title: "Claims Processing SOP", type: "PDF", size: "1.1 MB", tags: ["Claims", "SOP"], updated: "May 19, 2025", by: "Ops", tone: "red" },
    ],
    detail: {
      title: "Operation Phoenix Briefing",
      type: "PDF",
      size: "4.2 MB",
      updated: "May 24, 2025 09:14 AM",
      classification: "Confidential",
      docType: "Briefing",
      mission: "Operation Phoenix",
      tags: ["Briefing", "Phoenix", "Confidential", "+2"],
      uploadedBy: "Admin",
      dateAdded: "May 24, 2025 09:14 AM",
      checksum: "a7f3c2e8b1d90456...",
      path: "/library/briefings/operation-phoenix-briefing.pdf",
      pages: "1 / 24",
    },
  };

  const DATA = {
    financial,
    softdent,
    quickbooks,
    ar,
    claims,
    narratives,
    documents,
    library,
  };

  function get(pageId) {
    return DATA[pageId] || null;
  }

  return { DATA, get };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = PageSampleData;
}
if (typeof window !== "undefined") {
  window.PageSampleData = PageSampleData;
}
