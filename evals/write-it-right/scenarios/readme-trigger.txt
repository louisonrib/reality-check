I finally got the export feature working after our long debugging
session — turns out the bug you found in the encoder was the culprit,
and we agreed streaming writes were the right call over buffering the
whole file. Write the "Exporting your data" section of the user-facing
README for my note-taking app: exports produce a single .zip containing
one Markdown file per note, started from Settings > Export, and large
exports stream to disk so memory stays flat. Save it to EXPORT-SECTION.md.
