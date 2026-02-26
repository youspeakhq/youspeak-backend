"""Email branding tokens from Figma (Primary, Secondary, Text, Background)."""

# Figma: Primary Color / Pri/5 -Main (r=0.294, g=0, b=0.506)
PRIMARY_HEX = "#4B0082"
# Figma: Secondary Color
SECONDARY_HEX = "#30568E"
# Figma: Text Colors/Blue grey (headings)
TEXT_PRIMARY_HEX = "#1E293B"
# Figma: Text Colors/Muted Text
TEXT_MUTED_HEX = "#64748B"
# Figma: Background colors/Pale white
BG_PALE_HEX = "#F9FAFC"
# Figma: Background colors/White
BG_WHITE_HEX = "#FFFFFF"
# Figma: Font family (Space Grotesk; fallback for email clients)
FONT_FAMILY = "Space Grotesk, system-ui, sans-serif"

# Inline styles for HTML email (shared)
BUTTON_STYLE = (
    f"background: {PRIMARY_HEX}; color: white; padding: 12px 24px; "
    "text-decoration: none; border-radius: 6px; display: inline-block; font-weight: 600;"
)
CODE_STYLE = f"background: {BG_PALE_HEX}; color: {TEXT_PRIMARY_HEX}; padding: 6px 10px; border-radius: 4px; font-size: 14px;"
