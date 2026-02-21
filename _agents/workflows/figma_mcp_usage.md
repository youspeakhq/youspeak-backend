---
description: How to correctly use the Framelink MCP for Figma to extract design data
---

# Proper Usage of Framelink MCP for Figma

The Framelink Figma MCP server provides tools to extract design data, components, and layout information directly from a Figma URL.

## 1. Parsing the URL
When a user provides a Figma URL:
`https://www.figma.com/design/<fileKey>/<Project-Name>?node-id=<nodeId>&...`

- **fileKey:** Extract the alphanumeric string after `/design/` or `/file/`.
- **nodeId:** Extract the value of the `node-id` query parameter. **CRITICAL:** You must convert the hyphen `-` to a colon `:` (e.g., `3526-4167` becomes `3526:4167`).

## 2. Using the `get_figma_data` tool
Always use the specific `mcp_Framelink-MCP-for-Figma_get_figma_data` tool provided by the server.

- **Required parameter `fileKey`:** Provide the extracted fileKey.
- **Strongly Recommended parameter `nodeId`:** You MUST provide the converted `nodeId` if it exists in the URL. Fetching an entire file without a nodeId often returns overwhelmingly large or irrelevant data (like the brand canvas).
- **Parameter `depth`:** Do NOT provide the `depth` parameter unless the user explicitly requests a certain depth.

## 3. Interpreting the Output
The output represents a parsed node tree containing layout properties, text content, colors (fills), and component references.
- Look for `type: TEXT` to find textual content.
- Look for `type: FRAME` or `COMPONENT` for structure.
- If the output is saved to a file due to length, use `view_file` to read it and analyze the nested component structure carefully.
