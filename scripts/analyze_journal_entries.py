import argparse
import csv
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


REQUIRED_FIELDS = [
    "voucher_id",
    "date",
    "debit_account",
    "credit_account",
    "debit",
    "credit",
    "description",
    "posted_by",
    "entry_type",
]

HIGH_RISK_KEYWORDS = [
    "adjustment",
    "adjust",
    "reclass",
    "reclassification",
    "reverse",
    "reversal",
    "accrual",
    "write-off",
    "write off",
    "provision",
    "estimate",
    "true-up",
    "true up",
    "cleanup",
    "clean up",
    "temporary",
    "manual",
    "调整",
    "冲销",
    "重分类",
    "暂估",
    "补提",
    "计提",
    "清理",
    "平账",
    "暂挂",
]

VAGUE_TERMS = [
    "other",
    "misc",
    "processing",
    "cleanup",
    "clear",
    "temporary",
    "其他",
    "处理",
    "清理",
    "暂挂",
]

UNUSUAL_ACCOUNT_PAIRS = {
    ("Revenue", "Expense"),
    ("Expense", "Revenue"),
    ("Revenue", "Other Receivables"),
    ("Accrued Liabilities", "Revenue"),
    ("Intercompany Receivable", "Revenue"),
}

FLAG_LABELS = {
    "manual_entry": "手工分录",
    "period_end": "期末入账",
    "weekend_posting": "周末入账",
    "amount_above_p95": "金额高于P95",
    "amount_above_p99": "金额高于P99",
    "round_amount": "大额整数",
    "repeated_amount": "大额重复金额",
    "blank_description": "摘要为空",
    "vague_description": "摘要较模糊",
    "high_risk_keyword": "命中高风险关键词",
    "unusual_account_pair": "异常科目组合",
    "same_poster_approver": "制单人与审批人相同",
}


def read_csv(path):
    with Path(path).open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fieldnames):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_float(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def parse_date(value):
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def percentile(values, pct):
    values = sorted(v for v in values if v is not None)
    if not values:
        return 0
    if len(values) == 1:
        return values[0]
    rank = (len(values) - 1) * pct
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return values[int(rank)]
    return values[low] + (values[high] - values[low]) * (rank - low)


def normalize_entries(rows):
    normalized = []
    parse_issues = Counter()
    for row in rows:
        item = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
        item["_date"] = parse_date(item.get("date"))
        item["_debit"] = parse_float(item.get("debit"))
        item["_credit"] = parse_float(item.get("credit"))
        if item["_date"] is None:
            parse_issues["date_parse_failures"] += 1
        if item["_debit"] is None:
            parse_issues["debit_parse_failures"] += 1
        if item["_credit"] is None:
            parse_issues["credit_parse_failures"] += 1
        item["_amount"] = max(abs(item["_debit"] or 0), abs(item["_credit"] or 0))
        normalized.append(item)
    return normalized, parse_issues


def data_quality(entries, raw_fields, ledger_rows=None):
    missing_required_columns = [field for field in REQUIRED_FIELDS if field not in raw_fields]
    missing_counts = Counter()
    for row in entries:
        for field in REQUIRED_FIELDS:
            if field in raw_fields and str(row.get(field, "")).strip() == "":
                missing_counts[field] += 1

    total_debit = sum(row["_debit"] or 0 for row in entries)
    total_credit = sum(row["_credit"] or 0 for row in entries)
    dates = [row["_date"] for row in entries if row["_date"]]
    duplicate_keys = Counter(
        (
            row.get("voucher_id", ""),
            row.get("date", ""),
            row.get("debit_account", ""),
            row.get("credit_account", ""),
            f"{row['_debit'] or 0:.2f}",
            f"{row['_credit'] or 0:.2f}",
        )
        for row in entries
    )
    duplicate_count = sum(count - 1 for count in duplicate_keys.values() if count > 1)

    result = {
        "row_count": len(entries),
        "voucher_count": len({row.get("voucher_id", "") for row in entries}),
        "account_count": len(
            {row.get("debit_account", "") for row in entries}
            | {row.get("credit_account", "") for row in entries}
        ),
        "poster_count": len({row.get("posted_by", "") for row in entries}),
        "date_min": min(dates).isoformat() if dates else "",
        "date_max": max(dates).isoformat() if dates else "",
        "total_debit": total_debit,
        "total_credit": total_credit,
        "debit_credit_difference": total_debit - total_credit,
        "missing_required_columns": missing_required_columns,
        "missing_counts": dict(missing_counts),
        "duplicate_count": duplicate_count,
        "ledger_reconciliation": [],
    }

    if ledger_rows:
        je_totals = defaultdict(lambda: {"debit": 0.0, "credit": 0.0})
        for row in entries:
            je_totals[row.get("debit_account", "")]["debit"] += row["_debit"] or 0
            je_totals[row.get("credit_account", "")]["credit"] += row["_credit"] or 0

        ledger = {}
        for row in ledger_rows:
            account = row.get("account") or row.get("account_name") or row.get("account_code")
            if not account:
                continue
            ledger[account] = {
                "gl_debit": parse_float(row.get("gl_debit")) or 0,
                "gl_credit": parse_float(row.get("gl_credit")) or 0,
            }

        all_accounts = sorted(set(je_totals) | set(ledger))
        for account in all_accounts:
            je_debit = je_totals[account]["debit"]
            je_credit = je_totals[account]["credit"]
            gl_debit = ledger.get(account, {}).get("gl_debit", 0)
            gl_credit = ledger.get(account, {}).get("gl_credit", 0)
            result["ledger_reconciliation"].append(
                {
                    "account": account,
                    "je_debit": je_debit,
                    "gl_debit": gl_debit,
                    "debit_diff": je_debit - gl_debit,
                    "je_credit": je_credit,
                    "gl_credit": gl_credit,
                    "credit_diff": je_credit - gl_credit,
                }
            )
    return result


def is_round_amount(amount):
    return amount >= 100000 and abs(amount % 10000) < 0.01


def score_entries(entries):
    amounts = [row["_amount"] for row in entries]
    p95 = percentile(amounts, 0.95)
    p99 = percentile(amounts, 0.99)
    amount_counts = Counter(round(row["_amount"], 2) for row in entries)

    scored = []
    for row in entries:
        flags = []
        reasons = []
        score = 0
        amount = row["_amount"]
        desc = (row.get("description") or "").strip()
        desc_lower = desc.lower()
        date = row["_date"]
        debit_account = row.get("debit_account", "")
        credit_account = row.get("credit_account", "")

        def add(flag, points, reason):
            nonlocal score
            flags.append(flag)
            reasons.append(reason)
            score += points

        if (row.get("entry_type") or "").lower() == "manual":
            add("manual_entry", 20, "该分录为手工分录")
        if date and date.day >= 28:
            add("period_end", 15, "该分录在月末最后几天入账")
        if date and date.weekday() >= 5:
            add("weekend_posting", 10, "该分录在周末入账")
        if amount >= p99 and amount > 0:
            add("amount_above_p99", 25, f"金额高于P99阈值（{p99:,.2f}）")
        elif amount >= p95 and amount > 0:
            add("amount_above_p95", 15, f"金额高于P95阈值（{p95:,.2f}）")
        if is_round_amount(amount):
            add("round_amount", 10, "该分录为大额整数金额")
        if amount_counts[round(amount, 2)] > 1 and amount >= 100000:
            add("repeated_amount", 8, "该大额金额在总体中重复出现")
        if not desc:
            add("blank_description", 10, "摘要为空")
        elif len(desc) <= 12 or any(term in desc_lower for term in VAGUE_TERMS):
            add("vague_description", 10, "摘要较短或表述较模糊")
        matched_keywords = [kw for kw in HIGH_RISK_KEYWORDS if kw.lower() in desc_lower or kw in desc]
        if matched_keywords:
            add("high_risk_keyword", 15, "摘要命中高风险关键词：" + ", ".join(matched_keywords[:5]))
        if (debit_account, credit_account) in UNUSUAL_ACCOUNT_PAIRS:
            add("unusual_account_pair", 20, f"存在异常科目组合：{debit_account} -> {credit_account}")
        if row.get("approved_by") and row.get("posted_by") == row.get("approved_by"):
            add("same_poster_approver", 15, "制单人与审批人为同一人")

        suggestion = testing_suggestion(flags, row)
        scored_row = {
            "voucher_id": row.get("voucher_id", ""),
            "date": row.get("date", ""),
            "debit_account": debit_account,
            "credit_account": credit_account,
            "debit": f"{row['_debit'] or 0:.2f}",
            "credit": f"{row['_credit'] or 0:.2f}",
            "amount": f"{amount:.2f}",
            "description": desc,
            "posted_by": row.get("posted_by", ""),
            "approved_by": row.get("approved_by", ""),
            "entry_type": row.get("entry_type", ""),
            "risk_score": score,
            "risk_flags": "; ".join(flags),
            "risk_reasons": "; ".join(reasons),
            "suggested_documents": suggestion["documents"],
            "inquiry_questions": suggestion["questions"],
            "testing_steps": suggestion["steps"],
            "conclusion_placeholder": suggestion["conclusion"],
        }
        scored.append(scored_row)
    return scored, {"p95": p95, "p99": p99}


def testing_suggestion(flags, row):
    docs = set()
    questions = []
    steps = []
    if "manual_entry" in flags or "period_end" in flags:
        docs.update(["分录审批记录", "分录支持性文件", "管理层/财务人员说明"])
        questions.append("该分录为何采用手工方式或在期末入账？是否经过适当审批？")
        steps.append("检查分录审批记录、业务背景说明及相关支持性文件。")
    if "high_risk_keyword" in flags:
        docs.update(["调整计算表", "原始分录支持", "复核记录"])
        questions.append("摘要中提到的调整、重分类、冲销或计提对应什么业务事项？")
        steps.append("将调整金额追溯至计算表、原始单据或复核记录。")
    if "unusual_account_pair" in flags:
        docs.update(["会计处理说明", "科目映射依据", "业务支持文件"])
        questions.append("为什么该业务事项需要使用这一借贷科目组合？")
        steps.append("评估科目组合是否与业务实质一致，是否存在不寻常的重分类或利润调节迹象。")
    if "amount_above_p99" in flags or "amount_above_p95" in flags or "round_amount" in flags:
        docs.update(["金额计算过程", "合同/发票", "期后结算或回款记录"])
        questions.append("该金额如何确定？是否与合同、发票或计算表一致？")
        steps.append("重新计算金额，并与合同、发票、计算表或期后结算记录核对。")
    if "same_poster_approver" in flags:
        docs.update(["审批流记录", "职责分离说明"])
        questions.append("为什么该分录由同一人员制单并审批？是否存在审批流程绕过？")
        steps.append("检查审批流是否被覆盖，以及是否存在职责分离不足。")
    if not docs:
        docs.add("分录支持性文件")
        questions.append("该分录对应的业务背景是什么？")
        steps.append("检查支持性文件并记录业务合理性。")

    return {
        "documents": "; ".join(sorted(docs)),
        "questions": " ".join(questions),
        "steps": " ".join(steps),
        "conclusion": "待获取支持性文件及询问答复后形成初步判断。",
    }


def summarize(scored_rows):
    by_flag = Counter()
    by_month = defaultdict(lambda: {"count": 0, "amount": 0.0, "risk_score": 0})
    by_poster = defaultdict(lambda: {"count": 0, "amount": 0.0, "risk_score": 0})
    by_account = defaultdict(lambda: {"count": 0, "amount": 0.0, "risk_score": 0})
    for row in scored_rows:
        amount = float(row["amount"])
        score = int(row["risk_score"])
        month = row["date"][:7]
        by_month[month]["count"] += 1
        by_month[month]["amount"] += amount
        by_month[month]["risk_score"] += score
        by_poster[row["posted_by"]]["count"] += 1
        by_poster[row["posted_by"]]["amount"] += amount
        by_poster[row["posted_by"]]["risk_score"] += score
        by_account[row["debit_account"]]["count"] += 1
        by_account[row["debit_account"]]["amount"] += amount
        by_account[row["debit_account"]]["risk_score"] += score
        for flag in row["risk_flags"].split("; "):
            if flag:
                by_flag[flag] += 1
    return by_flag, by_month, by_poster, by_account


def table_lines(rows, headers):
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
    return lines


def follow_up_summary_rows(selected_rows):
    categories = [
        {
            "name": "期末/手工分录",
            "flags": {"manual_entry", "period_end"},
            "documents": "分录审批记录、业务背景说明、分录支持性文件、管理层/财务人员说明",
            "questions": "为什么采用手工方式或在期末入账？是否经过适当审批？",
            "steps": "检查审批记录、业务合理性、支持性文件及期后是否存在冲回或调整。",
        },
        {
            "name": "高风险关键词",
            "flags": {"high_risk_keyword"},
            "documents": "调整计算表、原始分录支持、复核记录、相关合同/发票",
            "questions": "摘要中的调整、重分类、冲销、计提或暂挂对应什么业务事项？",
            "steps": "将调整金额追溯至计算表、原始单据或复核记录，判断处理依据是否充分。",
        },
        {
            "name": "异常科目组合",
            "flags": {"unusual_account_pair"},
            "documents": "会计处理说明、科目映射依据、业务支持文件",
            "questions": "为什么该业务事项需要使用这一借贷科目组合？",
            "steps": "评估科目组合是否与业务实质一致，关注是否存在不合理重分类或利润调节迹象。",
        },
        {
            "name": "大额/整数/重复金额",
            "flags": {"amount_above_p95", "amount_above_p99", "round_amount", "repeated_amount"},
            "documents": "金额计算过程、合同/发票、期后结算或回款记录",
            "questions": "金额如何确定？是否与合同、发票或计算表一致？",
            "steps": "重新计算金额，并与合同、发票、计算表或期后结算记录核对。",
        },
        {
            "name": "制单审批同人",
            "flags": {"same_poster_approver"},
            "documents": "审批流记录、职责分离说明、管理层审批授权记录",
            "questions": "为什么该分录由同一人员制单并审批？是否存在审批流程绕过？",
            "steps": "检查审批控制是否被覆盖，以及是否存在职责分离不足。",
        },
        {
            "name": "摘要模糊或为空",
            "flags": {"blank_description", "vague_description"},
            "documents": "分录支持性文件、业务说明、相关沟通记录",
            "questions": "该分录的真实业务背景是什么？摘要为何未清晰描述？",
            "steps": "结合支持性文件补充业务背景，判断摘要模糊是否掩盖异常调整。",
        },
        {
            "name": "周末入账",
            "flags": {"weekend_posting"},
            "documents": "系统日志、过账审批记录、自动跑批说明",
            "questions": "该分录为何在非工作日入账？是否为系统自动生成？",
            "steps": "区分系统自动跑批和人工特殊处理，必要时检查过账权限和审批记录。",
        },
    ]

    rows = []
    for category in categories:
        matched = []
        for row in selected_rows:
            row_flags = set(flag for flag in row["risk_flags"].split("; ") if flag)
            if row_flags & category["flags"]:
                matched.append(row["voucher_id"])
        if matched:
            rows.append(
                {
                    "风险类型": category["name"],
                    "涉及样本": ", ".join(matched[:12]) + (" ..." if len(matched) > 12 else ""),
                    "样本数": len(matched),
                    "建议获取资料": category["documents"],
                    "建议询问问题": category["questions"],
                    "建议测试方向": category["steps"],
                }
            )
    return rows


def write_report(path, quality, parse_issues, thresholds, scored_rows, selected_rows):
    by_flag, by_month, by_poster, by_account = summarize(scored_rows)
    mismatch_rows = [
        r
        for r in quality["ledger_reconciliation"]
        if abs(r["debit_diff"]) > 0.01 or abs(r["credit_diff"]) > 0.01
    ]
    selected_amount = sum(float(r["amount"]) for r in selected_rows)
    total_amount = sum(float(r["amount"]) for r in scored_rows)
    lines = []
    lines.append("# JET会计分录风险分析报告")
    lines.append("")
    lines.append("## 一、总体概览")
    lines.extend(
        [
            f"- 分录行数：{quality['row_count']}",
            f"- 凭证数量：{quality['voucher_count']}",
            f"- 涉及科目数量：{quality['account_count']}",
            f"- 过账人数量：{quality['poster_count']}",
            f"- 数据期间：{quality['date_min']} 至 {quality['date_max']}",
            f"- 借方合计：{quality['total_debit']:,.2f}",
            f"- 贷方合计：{quality['total_credit']:,.2f}",
            f"- 借贷差异：{quality['debit_credit_difference']:,.2f}",
        ]
    )
    lines.append("")
    lines.append("## 二、数据质量检查")
    lines.extend(
        [
            f"- 缺失必要字段：{', '.join(quality['missing_required_columns']) or '无'}",
            f"- 关键字段空值：{quality['missing_counts'] or '无'}",
            f"- 日期/金额解析问题：{dict(parse_issues) or '无'}",
            f"- 重复行或重复凭证-科目-金额组合：{quality['duplicate_count']}",
            f"- 与总账核对差异科目数：{len(mismatch_rows)}",
        ]
    )
    if mismatch_rows:
        lines.append("")
        lines.append("### 总账核对差异")
        rows = []
        for r in mismatch_rows[:10]:
            rows.append(
                {
                    "科目": r["account"],
                    "借方差异": f"{r['debit_diff']:,.2f}",
                    "贷方差异": f"{r['credit_diff']:,.2f}",
                }
            )
        lines.extend(table_lines(rows, ["科目", "借方差异", "贷方差异"]))
    lines.append("")
    lines.append("## 三、风险评分概览")
    lines.extend(
        [
            f"- P95金额阈值：{thresholds['p95']:,.2f}",
            f"- P99金额阈值：{thresholds['p99']:,.2f}",
            f"- 高风险样本池数量：{len(selected_rows)} 条",
            f"- 高风险样本池金额合计：{selected_amount:,.2f}",
            f"- 高风险样本池金额占总体绝对金额比例：{(selected_amount / total_amount * 100 if total_amount else 0):.1f}%",
        ]
    )
    lines.append("")
    lines.append("## 四、风险标签分布")
    flag_rows = [{"风险标签": FLAG_LABELS.get(k, k), "命中次数": v} for k, v in by_flag.most_common()]
    lines.extend(table_lines(flag_rows, ["风险标签", "命中次数"]))
    lines.append("")
    lines.append("## 五、过账人风险画像")
    poster_rows = []
    for poster, data in sorted(by_poster.items(), key=lambda kv: kv[1]["risk_score"], reverse=True)[:10]:
        poster_rows.append(
            {
                "过账人": poster,
                "分录数": data["count"],
                "金额合计": f"{data['amount']:,.2f}",
                "风险分合计": data["risk_score"],
            }
        )
    lines.extend(table_lines(poster_rows, ["过账人", "分录数", "金额合计", "风险分合计"]))
    lines.append("")
    lines.append("## 六、月度风险画像")
    month_rows = []
    for month, data in sorted(by_month.items()):
        month_rows.append(
            {
                "月份": month,
                "分录数": data["count"],
                "金额合计": f"{data['amount']:,.2f}",
                "风险分合计": data["risk_score"],
            }
        )
    lines.extend(table_lines(month_rows, ["月份", "分录数", "金额合计", "风险分合计"]))
    lines.append("")
    lines.append("## 七、高风险样本池")
    selected_preview = []
    for row in selected_rows[:20]:
        selected_preview.append(
            {
                "凭证号": row["voucher_id"],
                "日期": row["date"],
                "金额": row["amount"],
                "风险分": row["risk_score"],
                "风险标签": "; ".join(FLAG_LABELS.get(flag, flag) for flag in row["risk_flags"].split("; ") if flag),
            }
        )
    lines.extend(table_lines(selected_preview, ["凭证号", "日期", "金额", "风险分", "风险标签"]))
    lines.append("")
    lines.append("## 八、后续处理建议汇总")
    lines.append("")
    lines.append("以下建议按风险类型聚合，用于快速确定后续核查方向；逐条样本的入选原因和处理建议详见 `selected_testing_pool.csv`。")
    lines.append("")
    follow_up_rows = follow_up_summary_rows(selected_rows)
    lines.extend(table_lines(follow_up_rows, ["风险类型", "涉及样本", "样本数", "建议获取资料", "建议询问问题", "建议测试方向"]))
    lines.append("")
    lines.append("## 九、使用说明")
    lines.append(
        "本报告用于形成优先核查清单。风险分和风险标签不代表最终审计结论，只用于解释哪些分录更值得优先跟进，以及后续应获取哪些资料、询问哪些问题。"
    )
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Analyze journal entries for JET risk scoring.")
    parser.add_argument("--entries", required=True, help="Path to journal entry CSV.")
    parser.add_argument("--ledger", help="Optional general ledger CSV for reconciliation.")
    parser.add_argument("--out-dir", default="reports", help="Directory for output files.")
    parser.add_argument("--score-threshold", type=int, default=45, help="Minimum score for selected testing pool.")
    parser.add_argument("--top-n", type=int, default=5, help="Always include top N entries by score.")
    args = parser.parse_args()

    raw_rows = read_csv(args.entries)
    raw_fields = raw_rows[0].keys() if raw_rows else []
    entries, parse_issues = normalize_entries(raw_rows)
    ledger_rows = read_csv(args.ledger) if args.ledger else None
    quality = data_quality(entries, raw_fields, ledger_rows)
    scored_rows, thresholds = score_entries(entries)
    scored_rows = sorted(scored_rows, key=lambda row: int(row["risk_score"]), reverse=True)

    selected_by_threshold = [row for row in scored_rows if int(row["risk_score"]) >= args.score_threshold]
    top_rows = scored_rows[: args.top_n]
    selected_ids = set()
    selected_rows = []
    for row in selected_by_threshold + top_rows:
        key = (row["voucher_id"], row["date"], row["debit_account"], row["credit_account"], row["amount"])
        if key not in selected_ids:
            selected_ids.add(key)
            selected_rows.append(row)
    selected_rows = sorted(selected_rows, key=lambda row: int(row["risk_score"]), reverse=True)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fields = list(scored_rows[0].keys()) if scored_rows else []
    write_csv(out_dir / "risk_scored_entries.csv", scored_rows, fields)
    write_csv(out_dir / "selected_testing_pool.csv", selected_rows, fields)
    write_report(out_dir / "jet_risk_report.md", quality, parse_issues, thresholds, scored_rows, selected_rows)

    print(f"Wrote {out_dir / 'risk_scored_entries.csv'}")
    print(f"Wrote {out_dir / 'selected_testing_pool.csv'}")
    print(f"Wrote {out_dir / 'jet_risk_report.md'}")


if __name__ == "__main__":
    main()
