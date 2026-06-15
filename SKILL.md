---
name: journal-entry-risk-analyzer
description: Analyze journal entry listings for audit-oriented transaction risk. Use when Codex needs to review JE/JET data, journal entry CSV or Excel exports, general ledger reconciliations, manual entries, suspicious accounting adjustments, risk scoring, testing pool selection, or follow-up testing suggestions.
---

# Journal Entry Risk Analyzer

Use this skill to turn a journal entry listing into an explainable transaction risk analysis. The goal is not to conclude fraud or replace audit judgment; it is to validate the population, identify higher-risk entries, generate a testing pool, and suggest follow-up procedures.

## Core Workflow

1. **Define the population**
   - Confirm the reporting period, source system, row count, voucher count, account count, preparer/poster count, total debits, and total credits.
   - If the user provides a general ledger or trial balance, reconcile journal entry totals by account to the ledger.
   - State any data limitations before interpreting risk results.

2. **Run data quality checks**
   - Check debit/credit balance.
   - Check missing values in key fields: date, voucher id, account, debit, credit, description, poster, entry source/type.
   - Check date and numeric parsing failures.
   - Check duplicate rows or repeated voucher-account-amount combinations.
   - Treat failed population checks as a risk to the analysis, not as a transaction exception by itself.

3. **Create risk features**
   Build features across these dimensions:
   - Time: period end entries, weekend entries, posting after close if close date is known.
   - Amount: high-value entries, round-number entries, repeated amounts.
   - Text: blank or vague descriptions, adjustment/reclass/reversal/accrual/write-off/provision/estimate keywords, Chinese equivalents such as 调整, 冲销, 重分类, 暂估, 补提, 计提, 清理, 平账.
   - Source and people: manual entries, unusual posters, preparer and approver being the same person if available.
   - Account pattern: unusual debit/credit combinations, large profit-and-loss adjustments, revenue/expense offsets, suspense or intercompany accounts.

4. **Build a risk profile**
   Before selecting samples, summarize risk distribution by month, poster, account, keyword, source/type, and risk flag. Use this to explain where risk is concentrated.

5. **Score and select the testing pool**
   - Assign transparent weights to each risk flag.
   - Produce `risk_score`, `risk_flags`, and `risk_reasons` for every entry.
   - Select entries by threshold or top-N ranking.
   - Preserve why each selected entry was included; audit testing needs explainability more than black-box precision.

6. **Generate follow-up actions**
   For each selected entry, generate:
   - Suggested supporting documents to request.
   - Questions for finance or the entry preparer.
   - Basic testing steps.
   - A short conclusion placeholder.

## Optional LLM Semantic Review

Static rules find known risk patterns. Add LLM review only for gray-zone entries, not for the full population by default.

Good gray-zone candidates:
- Medium rule score with vague text.
- Uncommon account combinations.
- Large entries whose descriptions avoid known keywords but sound like cleanup, true-up, temporary posting, or internal processing.
- Entries around period end that do not cross the high-risk threshold.

Ask the model to return structured fields only:
- `semantic_risk_label`
- `semantic_risk_reason`
- `suggested_follow_up`
- `confidence`

Do not present LLM output as a final audit conclusion. Treat it as an additional risk signal for human review.

## Scripted Quick Start

Use `scripts/analyze_journal_entries.py` for the deterministic MVP workflow:

```powershell
python scripts/analyze_journal_entries.py --entries assets/sample_journal_entries.csv --ledger assets/sample_general_ledger.csv --out-dir reports
```

Expected outputs:
- `risk_scored_entries.csv`: full population with risk scores and reasons.
- `selected_testing_pool.csv`: high-risk samples selected for follow-up.
- `jet_risk_report.md`: concise analysis report.

## Communication Guidance

Frame the work as transaction risk analysis:

> This workflow converts a manual JET process into a reusable data analysis pipeline: population validation, risk feature engineering, risk profiling, explainable scoring, and follow-up testing suggestions.

Avoid claiming the tool detects fraud. Say it prioritizes entries for review, explains why each entry was selected, and standardizes the next-step testing workflow.
