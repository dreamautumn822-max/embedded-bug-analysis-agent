from app.graph.nodes import (
    extract_bug_info_node,
    generate_hypotheses_node,
    generate_report_node,
    parse_logs_node,
    retrieve_related_docs_node,
    search_bug_history_node,
    search_codebase_node,
)


def _doc_retrieval_state():
    return {
        "symptom": "升级后 DHCP 客户端获取不到 IP",
        "module_hint": "dhcp",
        "bug_type": "network_dhcp",
        "extracted_info": {"keywords": ["dhcp", "lease"]},
        "parsed_logs": {"error_patterns": [], "events": []},
    }


def test_related_docs_node_uses_chroma_vector_results(monkeypatch):
    vector_results = [
        {
            "source": "dhcp.md",
            "score": 0.88,
            "snippet": "DHCP 地址池负责分配租约。",
            "content": "# DHCP\n\nDHCP 地址池负责分配租约。",
            "retrieval_method": "chroma_vector",
        }
    ]
    monkeypatch.setattr(
        "app.graph.nodes.retrieve_related_documents",
        lambda query: vector_results,
    )

    result = retrieve_related_docs_node(_doc_retrieval_state())

    assert result["related_docs"] == vector_results


def test_related_docs_node_falls_back_when_chroma_fails(monkeypatch):
    def fail_retrieval(query):
        raise RuntimeError("Chroma unavailable")

    monkeypatch.setattr(
        "app.graph.nodes.retrieve_related_documents",
        fail_retrieval,
    )

    result = retrieve_related_docs_node(_doc_retrieval_state())

    assert result["related_docs"]
    assert result["related_docs"][0]["source"] == "dhcp.md"
    assert result["related_docs"][0]["retrieval_method"] == "keyword_fallback"


def test_graph_nodes_produce_report_for_dhcp():
    state = {
        "device_model": "AX3000 Router",
        "firmware_version": "v2.1.8",
        "symptom": "升级后 DHCP 客户端偶发获取不到 IP",
        "logs": "\n".join(
            [
                "2026-06-25 14:03:11 netifd: interface lan reload",
                "2026-06-25 14:03:12 kernel: br-lan port state changed to blocking",
                "2026-06-25 14:03:12 dhcpd: lease allocation failed",
                "2026-06-25 14:03:14 kernel: br-lan port state changed to forwarding",
            ]
        ),
        "stack_trace": None,
        "module_hint": None,
        "extracted_info": {},
        "bug_type": "",
        "related_docs": [],
        "related_bugs": [],
        "related_code": [],
        "parsed_logs": {},
        "hypotheses": [],
        "evidence": [],
        "fix_suggestions": [],
        "final_report": "",
    }

    state.update(extract_bug_info_node(state))
    state.update(parse_logs_node(state))
    state.update(search_bug_history_node(state))
    state.update(search_codebase_node(state))
    state.update(retrieve_related_docs_node(state))
    state.update(generate_hypotheses_node(state))
    state.update(generate_report_node(state))

    assert state["bug_type"] == "network_dhcp"
    assert "lease allocation failed" in state["parsed_logs"]["error_patterns"]
    assert state["related_bugs"][0]["bug_id"] == "BUG-018"
    assert state["related_code"][0]["file"] == "netifd_reload.c"
    assert state["related_docs"][0]["source"] == "dhcp.md"
    assert any(item.startswith("log: ") for item in state["evidence"])
    assert any(item.startswith("doc: dhcp.md") for item in state["evidence"])
    assert "Bug 类型：network_dhcp" in state["final_report"]
