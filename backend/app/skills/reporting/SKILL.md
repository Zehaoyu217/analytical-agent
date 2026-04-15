---
name: reporting
description: "Build HTML reports, dashboards, and formatted tables from findings. Sub-skills: report_builder, dashboard_builder, html_tables."
version: "0.1"
---

# Reporting

Hub for output assembly. Use these sub-skills to produce structured deliverables from
analysis results.

## Choosing a sub-skill

| Task | Sub-skill |
|------|-----------|
| Assemble a multi-section HTML report with narrative | `report_builder` |
| Build an interactive dashboard from artifact IDs | `dashboard_builder` |
| Render a DataFrame or dict as a styled HTML table | `html_tables` |

## Workflow

Typically: analyze → promote findings → call `report_builder` or `dashboard_builder`
to assemble the output. `html_tables` is used inside report content, not standalone.
