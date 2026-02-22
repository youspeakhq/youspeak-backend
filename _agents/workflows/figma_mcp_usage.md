---
description: Use Figma MCP Bridge to get design data into the AI with no Figma API rate limits.
---

# Figma MCP Usage (Bridge)

[Figma MCP Bridge](https://github.com/gethopp/figma-mcp-bridge) streams live document data from a Figma plugin over WebSocket. **No Figma API calls** → no 429s, no rate limits.

## Setup (one-time)

1. **MCP config**  
   Ensure `figma-bridge` is in your MCP config (e.g. in Cursor):
   ```json
   "figma-bridge": {
     "command": "npx",
     "args": ["-y", "@gethopp/figma-mcp-bridge"]
   }
   ```

2. **Figma plugin**  
   - Open the [latest release](https://github.com/gethopp/figma-mcp-bridge/releases).  
   - Download the release and get `manifest.json` from the `plugin/` folder.  
   - In Figma: **Plugins → Development → Import plugin from manifest** and select that `manifest.json`.

## Every time you want to use it

1. Open the **Figma file** you care about.  
2. **Select the frame(s) or layers** you want the AI to read (e.g. click a frame in the canvas or Layers panel). If nothing is selected, the plugin has no data to send (see Troubleshooting).  
3. Run the **Figma MCP Bridge** plugin (Plugins → Figma MCP Bridge).  
4. Check the plugin window: it should show **"Selection: 1 node(s)"** (or more). If it shows **"Selection: 0 node(s)"**, go back to step 2 and select something.  
5. In Cursor, prompt as usual. The MCP tools use the **current selection**, not a URL.

## Troubleshooting

### "WebSocket Connected" but "Selection: 0 node(s)"

**Cause:** The Bridge is connected, but **no nodes are selected** in Figma. The plugin only sends data for the current selection. With 0 nodes selected, `get_design_context` / `get_selection` have nothing to return, so you may see timeouts or empty responses.

**Fix:** In Figma, click the **frame or component** you care about (in the canvas or in the **Layers** panel). Confirm the plugin window updates to **"Selection: 1 node(s)"** (or more). Then ask the AI again. Order matters: **select first**, then run the plugin (or run the plugin and then change selection).

## Notes

- Only **one** Figma tab can be connected to the Bridge at a time (one WebSocket per MCP server).  
- Data is **live**: whatever the plugin sees for the current selection is what the AI gets.  
- No `fileKey` or `nodeId` in prompts—the plugin uses the open file and current selection.
