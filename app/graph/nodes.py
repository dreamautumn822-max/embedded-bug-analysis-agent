import logging

from app.chains.extract_chain import extract_bug_info
from app.chains.report_chain import generate_report
from app.chains.root_cause_chain import generate_root_cause_hypotheses
from app.graph.state import BugAnalysisState
from app.llm.client import generate_root_cause_with_llm
from app.llm.config import LLMSettings
from app.paths import BUG_HISTORY_PATH, CODEBASE_DIR, DOCS_DIR
from app.rag.loader import load_markdown_docs
from app.rag.retriever import retrieve_related_documents
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
    return {"related_bugs": search_bug_history(query, BUG_HISTORY_PATH, limit=3)}


def search_codebase_node(state: BugAnalysisState) -> dict:
    query = " ".join(
        [
            state["symptom"],
            " ".join(state["extracted_info"].get("keywords", [])),
            " ".join(state["parsed_logs"].get("events", [])),
        ]
    )
    return {"related_code": search_codebase(query, CODEBASE_DIR, limit=3)}


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
            return {"related_docs": related_docs}
    except Exception as exc:
        logger.warning("Chroma retrieval failed; using keyword fallback: %s", exc)

    return {"related_docs": _keyword_related_documents(query)}


def _keyword_related_documents(query: str) -> list[dict]:
    query_tokens = _doc_tokens(query)
    related_docs: list[dict] = []

    for doc in load_markdown_docs(DOCS_DIR):
        doc_tokens = _doc_tokens(doc.page_content)
        score = len(query_tokens & doc_tokens)
        if score:
            related_docs.append(
                {
                    "source": doc.metadata["source"],
                    "score": score,
                    "snippet": _first_content_paragraph(doc.page_content),
                    "content": doc.page_content.strip(),
                    "retrieval_method": "keyword_fallback",
                }
            )

    related_docs.sort(key=lambda item: item["score"], reverse=True)
    return related_docs[:2]


def generate_hypotheses_node(state: BugAnalysisState) -> dict:
    settings = LLMSettings.from_env()
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
            )
            return {
                "hypotheses": [
                    hypothesis.model_dump() for hypothesis in llm_result.hypotheses
                ],
                "fix_suggestions": llm_result.fix_suggestions,
            }
        except Exception:
            pass

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
    else:
        fix_suggestions = ["补充完整日志、版本差异和模块信息后重新分析"]

    return {"hypotheses": hypotheses, "fix_suggestions": fix_suggestions}


def generate_report_node(state: BugAnalysisState) -> dict:
    evidence: list[str] = []
    evidence.extend([f"log: {item}" for item in state["parsed_logs"].get("evidence", [])[:3]])
    for doc in state["related_docs"][:2]:
        source = doc.get("source", "unknown")
        snippet = doc.get("snippet", "")
        evidence.append(f"doc: {source} - {snippet}")
    for bug in state["related_bugs"][:2]:
        bug_id = bug.get("bug_id", "unknown")
        root_cause = bug.get("root_cause", "missing root cause")
        evidence.append(f"bug: {bug_id} - {root_cause}")
    for code in state["related_code"][:2]:
        file_name = code.get("file", "unknown")
        line = code.get("line", "?")
        snippet = code.get("snippet", "")
        evidence.append(f"code: {file_name}:{line} - {snippet}")

    report = generate_report(
        bug_type=state["bug_type"],
        hypotheses=state["hypotheses"],
        evidence=evidence,
        fix_suggestions=state["fix_suggestions"],
    )
    return {"evidence": evidence, "final_report": report}


def _doc_tokens(text: str) -> set[str]:
    return {token.lower() for token in text.replace("-", " ").replace("_", " ").split()}


def _first_content_paragraph(content: str) -> str:
    for paragraph in content.split("\n\n"):
        stripped = paragraph.strip()
        if stripped and not stripped.startswith("#"):
            return " ".join(line.strip() for line in stripped.splitlines())
    return content.strip().splitlines()[0]
