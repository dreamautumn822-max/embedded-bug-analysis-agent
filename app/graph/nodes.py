import logging
import os

from langgraph.types import interrupt

from app.chains.extract_chain import extract_bug_info
from app.chains.report_chain import generate_report
from app.chains.root_cause_chain import generate_root_cause_hypotheses
from app.evidence import (
    bind_hypothesis_evidence,
    build_evidence_details,
    format_evidence,
)
from app.graph.state import BugAnalysisState
from app.llm.client import generate_root_cause_with_llm
from app.llm.config import LLMSettings
from app.rag.config import RAGSettings
from app.rag.loader import load_markdown_chunks
from app.rag.retriever import (
    content_snippet,
    retrieve_related_bugs,
    retrieve_related_code,
    retrieve_related_documents,
)
from app.tools.bug_history_search import search_bug_history
from app.tools.code_search import search_codebase
from app.tools.log_parser import parse_syslog


logger = logging.getLogger(__name__)


def extract_bug_info_node(state: BugAnalysisState) -> dict:
    extracted = extract_bug_info(
        symptom=state["symptom"],
        logs=state["logs"],
        module_hint=state["module_hint"],
    )
    return {"extracted_info": extracted, "bug_type": extracted["bug_type"]}


def parse_logs_node(state: BugAnalysisState) -> dict:
    parsed = parse_syslog(state["logs"])
    return {"parsed_logs": parsed}


def search_bug_history_node(state: BugAnalysisState) -> dict:
    query = " ".join(
        [
            state["symptom"],
            " ".join(state["extracted_info"].get("keywords", [])),
            " ".join(state["parsed_logs"].get("error_patterns", [])),
        ]
    )
    try:
        related_bugs = retrieve_related_bugs(query)
        if related_bugs:
            return {
                "related_bugs": related_bugs,
                **_retrieval_degradation(state, "search_bug_history", related_bugs),
            }
    except Exception as exc:
        logger.warning("Unified Bug retrieval failed; using keyword fallback: %s", exc)
        fallback = _fallback_reason(
            state,
            node="search_bug_history",
            code="bug_retrieval_failed",
            message="历史 Bug 混合检索失败，已切换到关键词检索。",
            error=exc,
        )
    else:
        fallback = _fallback_reason(
            state,
            node="search_bug_history",
            code="bug_retrieval_empty",
            message="历史 Bug 混合检索无结果，已切换到关键词检索。",
        )

    related_bugs = search_bug_history(
        query,
        RAGSettings.from_env().bug_history_path,
        limit=3,
    )
    return {
        "related_bugs": [
            _fallback_bug(bug, rank) for rank, bug in enumerate(related_bugs, 1)
        ],
        "fallback_reasons": fallback,
    }


def search_codebase_node(state: BugAnalysisState) -> dict:
    query = " ".join(
        [
            state["symptom"],
            " ".join(state["extracted_info"].get("keywords", [])),
            " ".join(state["parsed_logs"].get("events", [])),
        ]
    )
    try:
        related_code = retrieve_related_code(query)
        if related_code:
            return {
                "related_code": related_code,
                **_retrieval_degradation(state, "search_codebase", related_code),
            }
    except Exception as exc:
        logger.warning("Unified code retrieval failed; using keyword fallback: %s", exc)
        fallback = _fallback_reason(
            state,
            node="search_codebase",
            code="code_retrieval_failed",
            message="代码混合检索失败，已切换到关键词检索。",
            error=exc,
        )
    else:
        fallback = _fallback_reason(
            state,
            node="search_codebase",
            code="code_retrieval_empty",
            message="代码混合检索无结果，已切换到关键词检索。",
        )

    related_code = search_codebase(
        query,
        RAGSettings.from_env().codebase_dir,
        limit=3,
    )
    return {
        "related_code": [
            _fallback_code(code, rank) for rank, code in enumerate(related_code, 1)
        ],
        "fallback_reasons": fallback,
    }


def retrieve_related_docs_node(state: BugAnalysisState) -> dict:
    query = " ".join(
        [
            state["symptom"],
            " ".join(state["extracted_info"].get("keywords", [])),
            " ".join(state["parsed_logs"].get("error_patterns", [])),
            " ".join(state["parsed_logs"].get("events", [])),
        ]
    )
    try:
        related_docs = retrieve_related_documents(query)
        if related_docs:
            return {
                "related_docs": related_docs,
                **_retrieval_degradation(
                    state,
                    "retrieve_related_docs",
                    related_docs,
                ),
            }
    except Exception as exc:
        logger.warning("Chroma retrieval failed; using keyword fallback: %s", exc)
        fallback = _fallback_reason(
            state,
            node="retrieve_related_docs",
            code="document_retrieval_failed",
            message="模块文档混合检索失败，已切换到关键词检索。",
            error=exc,
        )
    else:
        fallback = _fallback_reason(
            state,
            node="retrieve_related_docs",
            code="document_retrieval_empty",
            message="模块文档混合检索无结果，已切换到关键词检索。",
        )

    return {
        "related_docs": _keyword_related_documents(query),
        "fallback_reasons": fallback,
    }


def _keyword_related_documents(query: str) -> list[dict]:
    settings = RAGSettings.from_env()
    query_tokens = _doc_tokens(query)
    related_docs: list[dict] = []

    for doc in load_markdown_chunks(
        settings.docs_dir,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    ):
        doc_tokens = _doc_tokens(doc.page_content)
        score = len(query_tokens & doc_tokens)
        if score:
            chunk_id = str(doc.metadata.get("chunk_id", "unknown"))
            related_docs.append(
                {
                    "source": doc.metadata["source"],
                    "section": doc.metadata.get("section", "document"),
                    "section_path": doc.metadata.get("section_path", "document"),
                    "parent_id": doc.metadata.get("parent_id", "unknown"),
                    "chunk_id": chunk_id,
                    "evidence_id": f"doc:{chunk_id}",
                    "score": score,
                    "snippet": content_snippet(doc.page_content),
                    "content": doc.page_content.strip(),
                    "retrieval_method": "keyword_fallback",
                }
            )

    related_docs.sort(key=lambda item: item["score"], reverse=True)
    for rank, item in enumerate(related_docs[:2], start=1):
        item["rank"] = rank
    return related_docs[:2]


def generate_hypotheses_node(state: BugAnalysisState) -> dict:
    settings = LLMSettings.from_env()
    evidence_details = build_evidence_details(state)
    if settings.is_ready:
        try:
            llm_result = generate_root_cause_with_llm(
                settings=settings,
                bug_type=state["bug_type"],
                symptom=state["symptom"],
                parsed_logs=state["parsed_logs"],
                related_bugs=state["related_bugs"],
                related_docs=state["related_docs"],
                related_code=state["related_code"],
                evidence_details=evidence_details,
            )
            return {
                "hypotheses": [
                    hypothesis.model_dump() for hypothesis in llm_result.hypotheses
                ],
                "fix_suggestions": llm_result.fix_suggestions,
                "generation_mode": "llm",
            }
        except Exception as exc:
            fallback_reasons = _fallback_reason(
                state,
                node="generate_hypotheses",
                code=_llm_fallback_code(exc),
                message="LLM 根因生成不可用，已切换到确定性规则链。",
                error=exc,
            )
    else:
        fallback_reasons = _fallback_reason(
            state,
            node="generate_hypotheses",
            code="llm_disabled",
            message="LLM 未启用或配置不完整，当前使用确定性规则链。",
        )

    hypotheses = generate_root_cause_hypotheses(
        bug_type=state["bug_type"],
        parsed_logs=state["parsed_logs"],
        related_bugs=state["related_bugs"],
        related_code=state["related_code"],
    )

    fix_suggestions = []
    if state["bug_type"] == "network_dhcp":
        fix_suggestions = [
            "在 br-lan 进入 forwarding/ready 状态后再启动 DHCP server",
            "为 DHCP server restart 增加 bridge 状态检查和有限重试",
            "补充升级后 LAN DHCP 获取地址回归测试",
        ]
    elif state["bug_type"] == "network_pppoe":
        fix_suggestions = [
            "WAN link up 事件中重新启动 PPPoE retry timer",
            "增加 link flap 后 PPPoE 状态机回归测试",
        ]
    elif state["bug_type"] == "wifi_disconnect":
        fix_suggestions = [
            "延迟 station table 清理直到 channel switch completed",
            "增加自动信道切换期间客户端保持连接测试",
        ]
    elif state["bug_type"] == "management_tr069":
        fix_suggestions = [
            "DNS 或 ACS 配置变化后清理 resolver cache",
            "补充 DNS reload 后 TR-069 Inform 回归测试",
        ]
    elif state["bug_type"] == "upgrade_regression":
        fix_suggestions = [
            "补齐旧配置键到新 schema 的显式迁移规则",
            "迁移后执行 schema 校验并生成差异报告",
            "补充跨版本升级与回滚回归测试",
        ]
    else:
        fix_suggestions = ["补充完整日志、版本差异和模块信息后重新分析"]

    return {
        "hypotheses": hypotheses,
        "fix_suggestions": fix_suggestions,
        "generation_mode": "rule",
        "fallback_reasons": fallback_reasons,
    }


def assess_review_node(state: BugAnalysisState) -> dict:
    threshold = _review_threshold()
    hypotheses = state.get("hypotheses", [])
    confidence = float(hypotheses[0].get("confidence", 0.0)) if hypotheses else 0.0
    evidence_types = {
        detail.get("evidence_type") for detail in build_evidence_details(state)
    }
    reasons: list[str] = []
    if state.get("bug_type") == "unknown":
        reasons.append("Bug 类型无法识别")
    if confidence < threshold:
        reasons.append(f"根因置信度 {confidence:.2f} 低于阈值 {threshold:.2f}")
    if len(evidence_types) < 2:
        reasons.append("有效证据类型少于 2 类")

    required = bool(reasons)
    return {
        "review_required": required,
        "review_status": "pending" if required else "not_required",
        "review_reasons": reasons,
    }


def queue_human_review_node(state: BugAnalysisState) -> dict:
    if not state.get("interactive_review", False):
        return {"review_status": "pending"}

    hypotheses = state.get("hypotheses", [])
    top_hypothesis = hypotheses[0] if hypotheses else None
    evidence_preview = [
        {
            "evidence_id": detail.get("evidence_id", "unknown"),
            "evidence_type": detail.get("evidence_type", "other"),
            "source": detail.get("source", "unknown"),
            "content": str(detail.get("content", ""))[:300],
            "section": detail.get("section"),
            "chunk_id": detail.get("chunk_id"),
            "symbol": detail.get("symbol"),
            "start_line": detail.get("start_line"),
            "end_line": detail.get("end_line"),
        }
        for detail in build_evidence_details(state)[:8]
    ]
    decision = interrupt(
        {
            "kind": "bug_analysis_review",
            "bug_type": state.get("bug_type", "unknown"),
            "generation_mode": state.get("generation_mode", "unknown"),
            "confidence": float(top_hypothesis.get("confidence", 0.0))
            if top_hypothesis
            else 0.0,
            "review_reasons": state.get("review_reasons", []),
            "top_hypothesis": top_hypothesis,
            "evidence_preview": evidence_preview,
        }
    )
    if not isinstance(decision, dict) or not isinstance(
        decision.get("approved"),
        bool,
    ):
        raise ValueError("Human review decision must contain a boolean approved field")

    normalized = {
        "approved": decision["approved"],
        "reviewer": str(decision.get("reviewer", "")).strip(),
        "comment": str(decision.get("comment") or "").strip() or None,
    }
    if not normalized["reviewer"]:
        raise ValueError("Human review decision must contain a reviewer")
    return {
        "review_status": "approved" if normalized["approved"] else "rejected",
        "review_decision": normalized,
    }


def route_after_review_assessment(state: BugAnalysisState) -> str:
    return "human_review" if state.get("review_required") else "auto_report"


def generate_report_node(state: BugAnalysisState) -> dict:
    evidence_details = build_evidence_details(state)
    evidence = [format_evidence(detail) for detail in evidence_details]
    hypotheses = bind_hypothesis_evidence(state["hypotheses"], evidence_details)

    report = generate_report(
        bug_type=state["bug_type"],
        hypotheses=hypotheses,
        evidence=evidence,
        fix_suggestions=state["fix_suggestions"],
    )
    review_decision = state.get("review_decision")
    if review_decision:
        decision_label = "通过" if review_decision.get("approved") else "驳回"
        report += (
            "\n\n## 人工复核\n"
            f"- 结论：{decision_label}\n"
            f"- 复核人：{review_decision.get('reviewer', 'unknown')}\n"
            f"- 备注：{review_decision.get('comment') or '无'}"
        )
    return {
        "hypotheses": hypotheses,
        "evidence": evidence,
        "evidence_details": evidence_details,
        "final_report": report,
    }


def _doc_tokens(text: str) -> set[str]:
    return {token.lower() for token in text.replace("-", " ").replace("_", " ").split()}


def _fallback_bug(bug: dict, rank: int) -> dict:
    bug_id = str(bug.get("bug_id", "unknown"))
    return {
        **bug,
        "source_type": "bug",
        "source": bug_id,
        "chunk_id": f"bug::{bug_id}",
        "evidence_id": f"bug:{bug_id}",
        "rank": rank,
        "retrieval_method": "keyword_fallback",
        "rerank_method": "none",
    }


def _fallback_code(code: dict, rank: int) -> dict:
    file_name = str(code.get("file", "unknown"))
    line = code.get("line", "?")
    return {
        **code,
        "source_type": "code",
        "source": file_name,
        "chunk_id": f"code::{file_name}::000",
        "evidence_id": f"code:{file_name}:{line}",
        "rank": rank,
        "retrieval_method": "keyword_fallback",
        "rerank_method": "none",
    }


def _fallback_reason(
    state: BugAnalysisState,
    *,
    node: str,
    code: str,
    message: str,
    error: Exception | None = None,
) -> list[dict]:
    reason = {"node": node, "code": code, "message": message}
    if error is not None:
        reason["error_type"] = type(error).__name__
    return [*state.get("fallback_reasons", []), reason]


def _llm_fallback_code(error: Exception) -> str:
    message = str(error).lower()
    if "invalid json" in message:
        return "llm_invalid_json"
    if "validation" in message:
        return "llm_schema_validation_failed"
    if "empty content" in message:
        return "llm_empty_response"
    return "llm_request_failed"


def _review_threshold() -> float:
    raw = os.getenv("AGENT_REVIEW_CONFIDENCE_THRESHOLD", "0.70")
    value = float(raw)
    if not 0.0 <= value <= 1.0:
        raise ValueError("AGENT_REVIEW_CONFIDENCE_THRESHOLD must be between 0 and 1")
    return value


def _retrieval_degradation(
    state: BugAnalysisState,
    node: str,
    results: list[dict],
) -> dict:
    warning_codes = {
        str(code)
        for result in results
        for code in result.get("retrieval_warnings", [])
    }
    if not warning_codes:
        return {}

    messages = {
        "vector_retrieval_failed": "向量召回失败，本次结果由 BM25 路径生成。",
        "bm25_retrieval_failed": "BM25 召回失败，本次结果由向量路径生成。",
        "model_reranker_failed": "模型重排失败，已切换到本地特征重排。",
    }
    fallback_reasons = list(state.get("fallback_reasons", []))
    for code in sorted(warning_codes):
        fallback_reasons.append(
            {
                "node": node,
                "code": code,
                "message": messages.get(code, "检索链路发生降级。"),
            }
        )
    return {"fallback_reasons": fallback_reasons}
