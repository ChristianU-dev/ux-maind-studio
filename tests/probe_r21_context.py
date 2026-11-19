"""Replay saved R20 receipts without inference. Requires the user's local snapshot."""
import argparse
from collections import Counter
from hashlib import sha256
from html import unescape
import json
from pathlib import Path
from contextlib import closing
import sqlite3

from docling_core.types.doc import DoclingDocument, DocItemLabel
from docling_graph.core.utils.doclang_format import serialize_doclang

from ux_maind.app import research
from ux_maind.app.a_status import dimensions
from ux_maind.app.evidence import Sources
from ux_maind.app.templates import Observation
from ux_maind.app.workspace import Workspace


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def normalized(text):
    return " ".join(unescape(text).split())


def request_text(request):
    return normalized("\n".join(message["text"] for message in request["messages"]))


def anchor_refs(result, observation):
    return [result["sources"][key]["ref"] for key in observation["source_ids"]]


def repeated_and_unattributed_sources():
    fixtures = {
        "transcript": ("Entry opened.", "Hard to find.", "Alternative entry opened.", "Hard to find."),
        "visual note": ("Control next to the arrow.", "It was unclear.", "Control in the footer.", "It was unclear."),
    }
    for name, nodes in fixtures.items():
        doc = DoclingDocument(name=name)
        if name == "visual note":
            doc.add_heading("Annotations", level=1)
        items = [doc.add_text(DocItemLabel.TEXT, text) for text in nodes]
        sources = Sources(doc, 1, "fixture")
        assert nodes[1] == nodes[3]
        anchors = [sources.locate(item.text, {"self_ref": item.self_ref}) for item in items[1::2]]
        assert anchors[0]["evidence_id"] != anchors[1]["evidence_id"]
        try:
            sources.locate(nodes[1], {})
        except ValueError:
            pass
        else:
            raise AssertionError("Ambiguous literal source must stay open")
        proposal = Observation(quote=nodes[1], statement=nodes[1])
        assert proposal.context.actor_or_speaker is None
        assert proposal.context.role is None


def replay(root, original, native, out):
    doc = DoclingDocument.load_from_json(native)
    ordered = [item for item, _ in doc.iterate_items()]
    assert len(ordered) == 40 and not doc.pages
    assert all(item.parent.cref == "#/body" and not item.prov for item in ordered)
    pairs = [(3, 5), (7, 9), (7, 11), (25, 27)]
    gold = [(ordered[context].self_ref, ordered[answer].self_ref) for context, answer in pairs]
    snippets = [
        "Adding in multiple counties",
        "understand the data lineage and metadata info",
        "Some tooltips are missing.",
    ]
    variants = [
        doc.export_to_markdown(),
        serialize_doclang(doc, add_location=False),
        serialize_doclang(doc, add_location=True),
    ]
    assert all(all(snippet in normalized(text) for snippet in snippets) for text in variants)
    assert "<location>" not in variants[1] and "<location>" not in variants[2]
    print("Native serializer sizes (Markdown, DocLang, DocLang-Geo):", [len(s) for s in variants])
    print("Gold pairs from original:", gold)
    with closing(sqlite3.connect((root / "workspace.sqlite").resolve().as_uri() + "?mode=ro", uri=True)) as db:
        for run, expected in {25: (19, 19, 15), 29: (41, 38, 36), 30: (21, 21, 21)}.items():
            document, value = db.execute("SELECT document, result FROM runs WHERE id = ?", (run,)).fetchone()
            r = json.loads(value)
            assert (r["source_sha256"], r["document_version"]) == (digest(original), digest(native))
            status = dimensions(r)
            assert (status["validated"], status["resolved"], status["graph_observations"]) == expected
            requests = r["native_graph"]["requests"]
            assert len(requests) == 2
            for request in requests:
                assert request["finish_reason"] == "stop"
                wire = request_text(request)
                assert all(s in wire for s in snippets)
                assert all(ordered[i].self_ref in wire for i in range(40))
            by_ref = {
                ref: o for o in r["observations"] for ref in anchor_refs(r, o)
                if ref in {answer for _, answer in gold}
            }
            assert set(by_ref) == {answer for _, answer in gold}
            for context, answer in gold:
                refs = [r["sources"][key]["ref"] for key in by_ref[answer]["context"]["source_ids"]]
                assert answer in refs and context not in refs
            print("A", run, expected, "requests with all refs:", len(requests),
                  "events:", dict(Counter(event["event_type"] for event in r["native_graph"]["trace"])))
        for run, stage in [(48, "B"), (55, "C")]:
            (value,) = db.execute("SELECT metadata FROM ux_objects WHERE id = ?", (run,)).fetchone()
            meta = json.loads(value)
            assert meta["stage"] == stage and meta["basis_runs"] == [30]
            assert meta["b_run"] == (48 if stage == "C" else None)
            requests = meta["native_graph"]["requests"]
            assert len(requests) == (20 if stage == "B" else 23)
            payloads = [request_text(request) for request in requests]
            contains_context = [all(s in text for s in snippets) for text in payloads]
            assert any(contains_context) and not all(contains_context)
            complete = [text for text in payloads if "=== COMPLETE DOCUMENT ===" in text]
            assert len(complete) == 1 and all(s in complete[0] for s in snippets)
            print(stage, run, "receipts:", len(requests),
                  "with all context:", sum(contains_context), "counts:", meta["counts"])

    workspace = Workspace(root)
    graph = research.graph(workspace, [document], basis={document: 30}, result_runs={"B": 48, "C": 55}, history=True)
    assert (len(graph["graph"]["nodes"]), len(graph["graph"]["edges"])) == (36, 31)
    records = {row["id"]: row for row in graph["objects"]}
    assert records[50]["effective"]["kind"] == "same_event"
    assert records[59]["review"] == "UNREVIEWED"
    out.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    repeated_and_unattributed_sources()
    print("PASS source identities, saved inputs, unresolved antecedent anchors, native projection and B/C receipt links.")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    for argument in ("workspace", "original", "native", "report"):
        cli.add_argument(argument, type=Path)
    args = cli.parse_args()
    replay(args.workspace, args.original, args.native, args.report)
