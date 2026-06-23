import styles from "./InsurancePatientBreakdown.module.css";

export function InsurancePatientBreakdown({ insurance, patient }: { insurance: number; patient: number }) {
  const total = insurance + patient;
  const insurancePercent = total > 0 ? Math.round((insurance / total) * 100) : 0;
  const patientPercent = total > 0 ? Math.round((patient / total) * 100) : 0;

  return (
    <section className="dashboard-insurance-patient-breakdown">
      <h3 className="dashboard-section-title">Insurance vs. Patient Payments</h3>
      <div className={styles["insurance-patient-bar"]}>
        <svg
          className={styles["insurance-patient-bar-svg"]}
          viewBox="0 0 100 32"
          preserveAspectRatio="none"
          role="img"
          aria-label={`Insurance ${insurancePercent} percent and patient ${patientPercent} percent`}
        >
          <rect className={styles["insurance-bar-fill"]} x="0" y="0" width={insurancePercent} height="32" />
          <rect className={styles["patient-bar-fill"]} x={insurancePercent} y="0" width={patientPercent} height="32" />
        </svg>
      </div>
      <div className={styles["insurance-patient-percentages"]}>
        <span className={styles["insurance-percentage"]}>Insurance: {insurancePercent}%</span>
        <span className={styles["patient-percentage"]}>Patient: {patientPercent}%</span>
      </div>
      <div className="insurance-patient-values">
        <span>Insurance: ${insurance.toLocaleString()}</span>
        <span>Patient: ${patient.toLocaleString()}</span>
      </div>
    </section>
  );
}
