# Journal Entry Risk Analyzer

Journal Entry Risk Analyzer is a lightweight JET (Journal Entry Testing) risk analysis project. It converts a manual journal entry review workflow into a reusable data analysis pipeline: population validation, risk feature engineering, explainable scoring, high-risk sample selection, and follow-up testing suggestions.

The project is designed as both a runnable Python MVP and a Codex Skill prototype.

## Why This Project

In a typical JET workflow, auditors or analysts may need to review thousands of journal entries exported from an ERP system. The process often relies on manual Excel filters, helper columns, pivot tables, and experience-based judgment.

This project standardizes that process into a repeatable SOP:

- Validate whether the journal entry population is complete and usable.
- Convert risk judgment into structured features.
- Score entries with transparent, explainable rules.
- Generate a high-risk testing pool.
- Suggest follow-up documents, inquiry questions, and testing directions.

The goal is not to automatically conclude fraud or misstatement. The goal is to prioritize which entries deserve human review and explain why.

## Analysis Framework

The workflow has five stages:

1. **Population validation**
   - Check date range, row count, voucher count, debit/credit balance, missing fields, duplicate rows, and optional reconciliation to the general ledger.

2. **Risk feature engineering**
   - Time features: period-end entries, weekend postings.
   - Amount features: high-value entries, round-number amounts, repeated amounts.
   - Text features: blank or vague descriptions, high-risk keywords.
   - People/source features: manual entries, same poster and approver.
   - Account-pattern features: unusual debit/credit account pairs.

3. **Risk profiling**
   - Summarize risk by flag, month, poster, and account to understand where risk is concentrated.

4. **Explainable risk scoring**
   - Assign transparent weights to risk flags and generate `risk_score`, `risk_flags`, and `risk_reasons`.

5. **Testing pool and follow-up suggestions**
   - Select high-risk entries and generate suggested documents, inquiry questions, and testing steps.

## Repository Structure

```text
journal-entry-risk-analyzer/
├── SKILL.md
├── README.md
├── agents/
│   └── openai.yaml
├── assets/
│   ├── sample_general_ledger.csv
│   └── sample_journal_entries.csv
├── references/
│   └── risk_rules.md
├── reports/
│   ├── jet_risk_report.md
│   ├── risk_scored_entries.csv
│   └── selected_testing_pool.csv
└── scripts/
    └── analyze_journal_entries.py
```

## Quick Start

Run the sample analysis:

```powershell
python scripts\analyze_journal_entries.py --entries assets\sample_journal_entries.csv --ledger assets\sample_general_ledger.csv --out-dir reports
```

Generated outputs:

- `reports/jet_risk_report.md`: Chinese summary report with risk profile and follow-up recommendation summary.
- `reports/risk_scored_entries.csv`: full population with risk scores, flags, reasons, and testing suggestions.
- `reports/selected_testing_pool.csv`: high-risk testing pool for follow-up review.

## Sample Output

The sample dataset includes 15 journal entries. The analyzer identifies a high-risk testing pool based on manual entries, period-end postings, large round amounts, vague descriptions, high-risk keywords, unusual account pairs, and same poster/approver patterns.

Example risk categories in the report:

- Period-end or manual entries
- High-risk keywords
- Unusual account combinations
- Large, round, or repeated amounts
- Same poster and approver
- Vague or blank descriptions
- Weekend postings

## Interview Story

This project can be explained as a transaction risk analysis workflow:

> I converted JET journal entry testing into a reusable data analysis pipeline. The tool first validates the journal entry population, then engineers risk features from time, amount, text, people, source, and account-pair dimensions. It produces explainable risk scores and a high-risk testing pool, then summarizes follow-up actions by risk type. The value is not replacing professional judgment, but improving the efficiency, consistency, and explainability of risk-based sample selection.

Core capabilities demonstrated:

- Data validation
- Feature engineering
- Rule-based anomaly detection
- Explainable risk scoring
- Prioritized sample selection
- Automated report generation

## Future Improvements

- Add optional LLM semantic review for gray-zone entries whose descriptions or account combinations look suspicious but do not strongly match static rules.
- Support Excel input/output in addition to CSV.
- Add charts for monthly risk trend, poster concentration, and risk flag distribution.
- Add configurable YAML rule weights.
- Add supporting-document matching by voucher ID, amount, date, or counterparty.

## Disclaimer

This project is a learning and workflow automation prototype. It does not provide audit conclusions and should not be used as a substitute for professional judgment, supporting-document review, or engagement-specific audit procedures.
