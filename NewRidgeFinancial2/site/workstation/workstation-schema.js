/**
 * NR2 Office Workstation — standalone program schema (not part of financial app nav).
 */
const WorkstationSchema = (function () {
  const SCHEMA_VERSION = "hal-10094";

  const PROGRAM = {
    id: "nr2-workstation",
    title: "NR2 Office Workstation",
    launcher: "StartWorkstation.bat",
    /** Loopback port for pywebview shell only — not for browser use. */
    port: 8766,
  };

  /** Measured SideNotesIM main window (SideNotesIM.exe on this office LAN). */
  const WINDOW = {
    width: 536,
    height: 447,
    minWidth: 480,
    minHeight: 400,
  };

  const practiceName = "New Ridge Family Dental";

  const STATION_GROUPS = [
    { id: "frontdesk", label: "Front Desk", members: ["Frontdesk 1", "Frontdesk 2"] },
    { id: "rooms", label: "All Rooms", members: ["Room 1", "Room 2", "Room 3", "Room 4", "Room 5"] },
    {
      id: "clinical",
      label: "Clinical + Lab",
      members: ["Room 1", "Room 2", "Room 3", "Room 4", "Room 5", "Darkroom"],
    },
    { id: "admin", label: "Admin", members: ["Office Manager", "Server"] },
    { id: "everyone", label: "Everyone", members: ["all"] },
  ];

  const page = {
    id: "workstation",
    label: "Workstation",
    title: "Office Workstation",
    subtitle: "Send messages between rooms or ask HAL",
    accent: "gold",
    practiceName,
    askHalSuggestions: [
      "What is the ADA code for dental office accessibility?",
      "How do I verify a patient's insurance eligibility?",
      "What is our cancellation and no-show policy?",
      "How do I handle a patient allergy or medical alert?",
    ],
    messagePrompts: [
      { label: "Patient arrived", template: "{station}: Patient has arrived" },
      { label: "Doctor ready", template: "{station}: Doctor is ready" },
      { label: "Need assistant", template: "{station}: Need assistant — " },
      { label: "Front desk", template: "{station}: Please send patient to front desk — " },
      { label: "Running behind", template: "{station}: Running behind — " },
      { label: "Blank message", template: "{station}: " },
      { label: "X-ray ready", template: "{station}: X-ray ready — " },
      { label: "Checkout", template: "{station}: Patient ready for checkout" },
      { label: "Sterilization", template: "{station}: Need instrument pick-up" },
      { label: "Break", template: "{station}: Stepping away — " },
      { label: "Confirm appt", template: "{station}: Please confirm appointment — " },
      { label: "Emergency", template: "{station}: URGENT — " },
    ],
  };

  const STATIONS = [
    "Frontdesk 1",
    "Frontdesk 2",
    "Office Manager",
    "Room 1",
    "Room 2",
    "Room 3",
    "Room 4",
    "Room 5",
    "Server",
    "Darkroom",
  ];

  function pageConfig() {
    return page;
  }

  return {
    SCHEMA_VERSION,
    PROGRAM,
    page,
    STATIONS,
    STATION_GROUPS,
    practiceName,
    WINDOW,
    pageConfig,
  };
})();

if (typeof globalThis !== "undefined") globalThis.WorkstationSchema = WorkstationSchema;
