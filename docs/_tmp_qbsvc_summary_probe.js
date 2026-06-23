const { createQuickBooksFinancialDataService } = require('c:/New folder/scripts/quickbooksFinancialDataService.js');
const service = createQuickBooksFinancialDataService({
  dbPath: 'C:/SoftDentFinancialExports/softdent_financial_analytics.db',
  staleAfterMinutes: 1440,
});
try {
  const result = service.getHalQuickBooksFinancialSummary({});
  require('fs').writeFileSync('c:/NewRidgeFamilyFinancial/docs/_tmp_qbsvc_summary_probe_out.json', JSON.stringify({ ok: true, keys: Object.keys(result), coverage: result.coverage }, null, 2));
} catch (error) {
  require('fs').writeFileSync('c:/NewRidgeFamilyFinancial/docs/_tmp_qbsvc_summary_probe_out.json', JSON.stringify({ ok: false, message: error.message, stack: error.stack }, null, 2));
}
