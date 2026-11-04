"""Builder for the pre-installed Song Timestamp Studio canvas.

The graph references the TimestampStudio node pack plus ComfyUI's native
LoadAudio / PreviewAudio nodes. Every stage is a real, individually executed
node on a visible, connected graph — nothing is collapsed into one wrapper.

    1 LoadAudio          native — upload the song (WAV / FLAC / MP3)
    2 STSLyricsOptions   your lyrics + model / language / isolation / song name
    3 STSAlign           forced alignment  ← audio + opts
    4 STSNudge           shift everything at once
    5 STSExportAll       every format + ZIP into the output folder
    6 STSAudition        ~8 s around one line  ← result
    7 PreviewAudio       native — hear the audition
"""
import copy
import json

HEADER = "Song Timestamp Studio — your lyrics onto exact seconds"


def _node(nodes, nid, kind, pos, inputs, outputs, widgets, size=(340, 120), title=None):
    node = {"id": nid, "type": kind, "pos": list(pos), "size": list(size), "flags": {},
            "order": len(nodes), "mode": 0,
            "inputs": [{"name": name, "type": typ, "link": None} for name, typ in inputs],
            "outputs": [{"name": name, "type": typ, "links": []} for name, typ in outputs],
            "properties": {"Node name for S&R": kind}, "widgets_values": widgets}
    if title:
        node["title"] = title
    nodes.append(node)
    return node


def _wire(nodes, links, pairs):
    lookup = {n["id"]: n for n in nodes}
    for src, out_slot, dst, input_name in pairs:
        source = lookup[src]
        target = lookup[dst]
        slot = next(i for i, x in enumerate(target["inputs"]) if x["name"] == input_name)
        ident = len(links) + 1
        typ = source["outputs"][out_slot]["type"]
        links.append([ident, src, out_slot, dst, slot, typ])
        source["outputs"][out_slot]["links"].append(ident)
        target["inputs"][slot]["link"] = ident


def _finish(nodes, links):
    return {"last_node_id": max(n["id"] for n in nodes),
            "last_link_id": len(links), "nodes": nodes, "links": links,
            "groups": [], "config": {}, "extra": {"ds": {"scale": 0.65, "offset": [40, 60]},
                                                  "sts_title": HEADER},
            "version": 0.4}


def build_studio_canvas(example_lyrics):
    nodes, links = [], []
    _node(nodes, 1, "LoadAudio", (40, 120), [], [("AUDIO", "AUDIO")], ["", "audio"],
          (420, 180), title="1 · Upload your song (WAV / FLAC / MP3)")
    _node(nodes, 2, "STSLyricsOptions", (40, 420), [], [("STS_OPTS", "STS_OPTS")],
          ["my_song", example_lyrics, "auto", "auto", False], (440, 420),
          title="2 · Your lyrics (keep the [Verse] / [Chorus] tags)")
    _node(nodes, 3, "STSAlign", (560, 240),
          [("audio", "AUDIO"), ("opts", "STS_OPTS")], [("STS_RESULT", "STS_RESULT")], [],
          (420, 160), title="3 · Forced alignment — your words onto exact seconds")
    _node(nodes, 4, "STSNudge", (1040, 120), [("result", "STS_RESULT")],
          [("STS_RESULT", "STS_RESULT")], [0.0], (360, 140),
          title="4 · All times late? early? shift everything at once")
    _node(nodes, 5, "STSExportAll", (1460, 120), [("result", "STS_RESULT")], [],
          (420, 220), title="5 · Export LRC · SRT · VTT · chapters · REAPER · Cut Plan · ZIP")
    _node(nodes, 6, "STSAudition", (1040, 380), [("result", "STS_RESULT")],
          [("AUDIO", "AUDIO")], [1, 1.5], (360, 160),
          title="6 · Hear one line — does the vocal enter on time?")
    _node(nodes, 7, "PreviewAudio", (1460, 420), [("audio", "AUDIO")], [], ["audio"],
          (420, 140), title="7 · Ear check player")
    _wire(nodes, links, [(1, 0, 3, "audio"), (2, 0, 3, "opts"), (3, 0, 4, "result"),
                         (4, 0, 5, "result"), (3, 0, 6, "result"), (6, 0, 7, "audio")])
    return _finish(nodes, links)


def build_canvases(example_lyrics):
    return {"studio": build_studio_canvas(example_lyrics)}


if __name__ == "__main__":
    import os

    os.environ["STS_AUTOLAUNCH"] = "0"
    import sys

    sys.path.insert(0, "/home/z/my-project/scripts")
    import timestamp_studio as sts

    graph = build_studio_canvas(sts.EXAMPLE_LYRICS)
    print(json.dumps(graph, indent=1)[:600])
    print("nodes:", len(graph["nodes"]), "links:", len(graph["links"]))
