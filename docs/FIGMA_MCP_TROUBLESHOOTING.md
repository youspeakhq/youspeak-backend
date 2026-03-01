# Figma MCP – Timeout and connection troubleshooting

When Figma MCP calls (e.g. `get_document`, `get_design_context`) time out or fail, use this checklist. Based on [Figma Developer Docs](https://developers.figma.com/docs/figma-mcp-server/) and community reports (Feb 2025).

---

## Why timeouts happen

1. **Selection too large** – The most common cause. Large or deeply nested frames produce huge responses and can overwhelm the context window or cause the AI agent (Cursor) to time out. Figma docs: [Stuck or too slow](https://developers.figma.com/docs/figma-mcp-server/stuck-or-slow/), [Avoid large frames](https://developers.figma.com/docs/figma-mcp-server/avoid-large-frames/).
2. **Agent-side timeout** – Errors like “lost connection to MCP server” often come from **Cursor** (or the AI) timing out or misinterpreting context, not from the Figma MCP server itself. The MCP server runs locally.
3. **Connection / tokens** – In Cursor, expired or corrupted MCP tokens can cause tool call failures. Figma docs: [Known issues with MCP clients](https://developers.figma.com/docs/figma-mcp-server/mcp-clients-issues/).
4. **Server not running** – The Figma Dev Mode MCP server only runs when the file is **open in the Figma desktop app** and MCP is enabled in Dev Mode.

---

## Checklist (in order)

1. **Figma desktop**
   - Figma **desktop app** is running (not only browser).
   - The **correct file** is open (e.g. “Indiigoo Labs _You Speak_ AI language assistant”).
   - **Dev Mode** is on → **MCP** section is **enabled**.

2. **Smaller selection (if using selection-based tools)**
   - Select a **specific frame or component** (e.g. “Room Monitor” frame) instead of the whole page or document.
   - Prefer `get_design_context` or `get_node` with a **node ID** for a single frame rather than `get_document` (whole document can be very large).

3. **Cursor: clear MCP tokens**
   - Command Palette (`Cmd+Shift+P` / `Ctrl+Shift+P`) → **“Clear All MCP Tokens”**.
   - Re-authenticate when prompted.
   - **Restart Cursor** fully after clearing tokens.

4. **Restart**
   - Restart **Figma desktop app**.
   - Restart **Cursor**.

5. **Network**
   - If using VPN/proxy, ensure **figma.com** (and any Figma APIs) are not blocked.

6. **Debug (if still failing)**
   - In Cursor/VS Code: Command Palette → **“Figma: Save Debug Information”** and inspect the saved logs.

---

## For this project

- When fetching **Room Monitor** (or any specific screen), prefer selecting that **frame in Figma** and using **`get_design_context`** (or `get_node` with its node ID) instead of `get_document`.
- If you have a **node ID** for the Room Monitor frame (e.g. from design docs), use it so the request is scoped and less likely to time out.
