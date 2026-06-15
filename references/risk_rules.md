# JET Risk Rule Reference

Use these rules as a starting point. Adjust thresholds to the engagement context, materiality, business model, and known risk areas.

## Data Quality Checks

| Check | Purpose |
| --- | --- |
| Date range coverage | Confirm the listing covers the intended period. |
| Debit/credit balance | Confirm the exported population is internally consistent. |
| Key field completeness | Identify missing fields that weaken risk analysis. |
| Numeric/date parsing | Catch text-formatted dates or amounts before scoring. |
| Ledger reconciliation | Reconcile journal entry totals by account to general ledger totals when available. |

## Risk Flags

| Flag | Default Weight | Rationale |
| --- | ---: | --- |
| Manual entry | 20 | Manual postings are more judgmental and easier to use for adjustments. |
| Period-end entry | 15 | Period-end entries are more likely to affect reporting cutoffs. |
| Weekend entry | 10 | Non-business-day posting may indicate special handling. |
| Amount above P95 | 15 | Large entries deserve priority review. |
| Amount above P99 | 25 | Extreme entries can drive material misstatement risk. |
| Round amount | 10 | Large round amounts may indicate estimates or manual adjustments. |
| Vague or blank description | 10 | Weak descriptions reduce business rationale transparency. |
| High-risk keyword | 15 | Adjustment, reclass, reversal, accrual, write-off, provision, and estimate terms often indicate judgmental entries. |
| Repeated amount | 8 | Repeated values can indicate duplicated, recurring, or templated adjustments. |
| Unusual account pair | 20 | Uncommon debit/credit combinations may lack normal business logic. |
| Same preparer and approver | 15 | Weak segregation of duties increases override risk. |

## Suggested Follow-Up Mapping

| Risk Type | Suggested Documents | Suggested Questions |
| --- | --- | --- |
| Manual period-end adjustment | Approval evidence, calculation support, management rationale, subsequent reversal evidence | Why was it posted at period end? Who approved it? Is it recurring or one-off? |
| Reclass or correction | Original entry, reclassification basis, reviewer approval, account mapping | What error or presentation issue was corrected? Why is this account pair appropriate? |
| Accrual or estimate | Accrual schedule, contract, invoice received after period end, calculation file | What assumptions were used? Was the estimate updated after year end? |
| Write-off or provision | Aging report, impairment memo, approval record, collection history | What triggered the write-off/provision? Is the basis consistent with policy? |
| Unusual account pair | Supporting documents, journal explanation, account policy | What business event does this represent? Why are these accounts paired? |
