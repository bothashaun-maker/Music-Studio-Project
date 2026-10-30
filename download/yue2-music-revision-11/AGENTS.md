# User preferences and continuity

- Preserve working behavior. Prefer scoped, additive improvements; do not remove
  working access routes or change model/generation defaults incidentally.
- User explicitly wants original WAV uploads preserved, without requiring file
  conversion. Cloudflare is additional to the existing Gradio share route.
- Existing Kaggle asset datasets must remain usable for this access-only update.
- Publish authorized notebook changes to bothashaun-maker/Music, including sources
  and regenerated notebooks, after relevant local checks. Report GPU/network
  validation limits honestly. Do not push music changes to Movies.
- Source: native_yue2/; builder: tools/build_fast_notebook.py.
- Give concise instructions, one step at a time when guiding the user's screen.

## ComfyUI canvas wrapper (2026-10-30)

- The user's YuE2 asset dataset is built, working, and must not be rebuilt for
  wrapper work. Model weights always come from the dataset ("as-is").
- The user asked for the Cloudflare link to open a normal ComfyUI canvas with
  the YuE2 workflow — nodes, models, everything — exactly like the Movies H3
  canvases: persistent ComfyUI, full visible node graph, workflows pre-installed
  in the menu, nothing collapsed into one wrapper node, no auto-render.
- Decision (user-selected): wrap the proven native FP16 engine as real
  ComfyUI nodes (KaggleYuE2 pack), NOT the official ComfyUI YuE2 nodes; keep
  the Gradio wrapper as a second route; canvases = Full Song + Cover/Restyle.
- Both wrappers share one engine lock; each hands over to the other
  (verified stop / /yue2/release). Same saved-run artifact schema.
- ComfyUI pinned to v0.43.2 (423cbd20511becb1f16122ab518e92e58bfa03d9),
  session-only, requirements under the Kaggle constraints file.
- Revision 11 = this canvas wrapper. Delivery of revision 11 was a full-repo
  ZIP for the user to upload via GitHub's web UI (no push credentials).
