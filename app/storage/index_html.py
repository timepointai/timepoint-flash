"""Self-contained HTML index page generator for blob folders.

Uses string.Template for zero-dependency HTML generation.

Examples:
    >>> from app.storage.index_html import generate_index_html
    >>> html = generate_index_html(manifest)
"""

from __future__ import annotations

from string import Template
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.storage.manifest import BlobManifest

_TEMPLATE = Template("""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>$title</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #0a0a0a; color: #e0e0e0; padding: 2rem; max-width: 960px; margin: 0 auto; }
  h1 { font-size: 1.6rem; margin-bottom: 0.25rem; color: #fff; }
  .subtitle { color: #888; font-size: 0.9rem; margin-bottom: 1.5rem; }
  .image-container { margin: 1.5rem 0; text-align: center; }
  .image-container img { max-width: 100%; border-radius: 8px; border: 1px solid #333; }
  .section { background: #151515; border: 1px solid #262626; border-radius: 8px;
             padding: 1.25rem; margin-bottom: 1rem; }
  .section h2 { font-size: 1rem; color: #aaa; margin-bottom: 0.75rem;
                 text-transform: uppercase; letter-spacing: 0.05em; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 0.5rem; }
  .kv { padding: 0.4rem 0; }
  .kv .label { color: #666; font-size: 0.8rem; }
  .kv .value { color: #ccc; font-size: 0.95rem; }
  .files { list-style: none; }
  .files li { padding: 0.3rem 0; border-bottom: 1px solid #1a1a1a; font-size: 0.9rem; }
  .files li:last-child { border-bottom: none; }
  .file-size { color: #666; float: right; }
  .badge { display: inline-block; background: #1a3a1a; color: #4ade80; padding: 0.15rem 0.5rem;
           border-radius: 4px; font-size: 0.75rem; margin-right: 0.25rem; }
  .badge.stub { background: #3a2a1a; color: #fbbf24; }
  .footer { text-align: center; color: #444; font-size: 0.75rem; margin-top: 2rem; }
  a { color: #60a5fa; text-decoration: none; }
  a:hover { text-decoration: underline; }
</style>
</head>
<body>
<h1>$title</h1>
<p class="subtitle">$query &mdash; $year $era $location</p>

$image_section

<div class="section">
  <h2>Temporal</h2>
  <div class="grid">
    <div class="kv"><div class="label">Year</div><div class="value">$year</div></div>
    <div class="kv"><div class="label">Era</div><div class="value">$era</div></div>
    <div class="kv"><div class="label">Location</div><div class="value">$location</div></div>
    <div class="kv"><div class="label">Render Type</div><div class="value">$render_type</div></div>
  </div>
</div>

<div class="section">
  <h2>Provenance</h2>
  <div class="grid">
    <div class="kv"><div class="label">Text Model</div><div class="value">$text_model</div></div>
    <div class="kv"><div class="label">Image Model</div><div class="value">$image_model</div></div>
    <div class="kv"><div class="label">Generator</div><div class="value">$generator v$generator_version</div></div>
    <div class="kv"><div class="label">Generated</div><div class="value">$generated_at</div></div>
    <div class="kv"><div class="label">Source Type</div><div class="value">$digital_source_type</div></div>
  </div>
</div>

<div class="section">
  <h2>Files ($file_count)</h2>
  <ul class="files">
$file_list
  </ul>
  <p style="margin-top:0.75rem;color:#666;font-size:0.85rem;">Total: $total_size</p>
</div>

<div class="section">
  <h2>Status</h2>
  <div class="grid">
    <div class="kv"><div class="label">Version</div><div class="value">$generation_version</div></div>
    <div class="kv"><div class="label">Sequence</div><div class="value">$sequence_id</div></div>
    <div class="kv"><div class="label">NSFW</div><div class="value">$nsfw_flag</div></div>
  </div>
  <div style="margin-top:0.75rem;">
    <span class="badge stub">Cloud Storage: coming soon</span>
    <span class="badge stub">C2PA: coming soon</span>
    <span class="badge stub">VR/Spatial: coming soon</span>
  </div>
</div>

<div class="footer">
  TIMEPOINT Flash v$generator_version &middot;
  <a href="manifest.json">manifest.json</a> &middot;
  Generated $generated_at
</div>
</body>
</html>
""")


def _format_bytes(n: int) -> str:
    """Format byte count to human-readable string."""
    if n < 1024:
        return f"{n} B"
    elif n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    else:
        return f"{n / (1024 * 1024):.1f} MB"


def generate_index_html(manifest: "BlobManifest") -> str:
    """Generate a self-contained HTML index page from a manifest.

    Args:
        manifest: BlobManifest with full metadata.

    Returns:
        Complete HTML string.
    """
    # Build file list HTML
    file_lines = []
    for f in manifest.files:
        size_str = _format_bytes(f.size_bytes)
        file_lines.append(
            f'    <li><a href="{f.filename}">{f.filename}</a>'
            f'<span class="file-size">{size_str}</span></li>'
        )
    file_list = "\n".join(file_lines) if file_lines else "    <li>No files</li>"

    # Image section
    image_filename = None
    for f in manifest.files:
        if f.filename.startswith("image."):
            image_filename = f.filename
            break

    if image_filename:
        image_section = (
            f'<div class="image-container">\n'
            f'  <img src="{image_filename}" alt="{manifest.query}">\n'
            f'</div>'
        )
    else:
        image_section = ""

    return _TEMPLATE.substitute(
        title=manifest.folder_name,
        query=manifest.query,
        year=manifest.temporal.year or "Unknown",
        era=manifest.temporal.era or "",
        location=manifest.temporal.location or "Unknown",
        render_type=manifest.render_type,
        text_model=manifest.provenance.text_model or "Unknown",
        image_model=manifest.provenance.image_model or "None",
        generator=manifest.provenance.generator,
        generator_version=manifest.provenance.generator_version,
        generated_at=manifest.provenance.generated_at or "Unknown",
        digital_source_type=manifest.provenance.digital_source_type,
        file_count=len(manifest.files),
        file_list=file_list,
        total_size=_format_bytes(manifest.total_size_bytes),
        generation_version=manifest.generation_version,
        sequence_id=manifest.sequence.sequence_id or "None",
        nsfw_flag="Yes" if manifest.content_flags.nsfw_flag else "No",
        image_section=image_section,
    )
