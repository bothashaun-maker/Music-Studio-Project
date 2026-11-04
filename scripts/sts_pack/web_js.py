"""Frontend extension source for the TimestampStudio node pack.

STS_OPEN_WORKFLOW_JS is written to custom_nodes/TimestampStudio/web/open_workflow.js
at setup time. The Cloudflare link carries ?sts_workflow=studio; the extension
loads that canvas once ComfyUI finishes mounting, then strips the parameter so
refreshes preserve subsequent edits. Same proven pattern as the YuE2 / H3 links.
"""

STS_OPEN_WORKFLOW_JS = """import { app } from "../../scripts/app.js";

const WORKFLOWS = {
    studio: { file: "sts-studio.json",
              require: "STSExportAll",
              title: "Song Timestamp Studio" },
};

app.registerExtension({
    name: "TimestampStudio.OpenWorkflow",
    setup() {
        const url = new URL(window.location.href);
        const name = url.searchParams.get("sts_workflow");
        if (!name || !Object.prototype.hasOwnProperty.call(WORKFLOWS, name)) return;
        const spec = WORKFLOWS[name];
        const open = async () => {
            try {
                // Let ComfyUI finish mounting and restoring its previous tab first.
                const deadline = Date.now() + 60000;
                while (!app.vueAppReady || !app.positionConversion) {
                    if (Date.now() > deadline) throw new Error("ComfyUI did not finish starting.");
                    await new Promise((resolve) => setTimeout(resolve, 100));
                }
                await new Promise((resolve) => setTimeout(resolve, 500));
                const response = await fetch(new URL(spec.file, import.meta.url), { cache: "no-store" });
                if (!response.ok) throw new Error(`Canvas download failed: ${response.status}`);
                const graph = await response.json();
                const types = new Set((graph.nodes || []).map((node) => node.type));
                if (!types.has(spec.require) || !types.has("STSAlign")) {
                    throw new Error("The installed Timestamp Studio canvas is incomplete.");
                }
                await app.loadGraphData(graph, true, true, (graph.extra?.sts_title || spec.title) + ".json");
                // Newer frontends pop the Templates dialog over the loaded canvas;
                // dismiss it so the graph is immediately visible.
                for (const delay of [200, 800]) {
                    setTimeout(() => {
                        const closer = document.querySelector(".p-dialog-close-button, [data-testid='close-button']");
                        if (closer instanceof HTMLElement) closer.click();
                        else window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", code: "Escape", bubbles: true }));
                    }, delay);
                }
                // Refreshes must preserve subsequent edits rather than reload the template.
                url.searchParams.delete("sts_workflow");
                window.history.replaceState(null, "", url);
            } catch (error) {
                console.error("Could not open the Timestamp Studio canvas", error);
                window.alert(`Could not open the Timestamp Studio canvas: ${error.message}`);
            }
        };
        // Do not block ComfyUI setup while waiting for its mounted state.
        void open();
    },
});
"""
