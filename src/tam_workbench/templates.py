from __future__ import annotations

from pathlib import Path

DEFAULT_TEMPLATES = {
    "customer_email.md": """# Customer Issue Acknowledgement: {{title}}

Hi {{customer_name}},

Thank you for raising this. I understand the issue is:

## Summary
{{summary}}

## What We Are Checking
{{investigation_plan}}

## What I Need From You
{{customer_questions}}

## Next Update
{{next_update}}
""",
    "internal_escalation.md": """# Internal Escalation: {{title}}

## Account
{{account_name}}

## Summary
{{summary}}

## Business Impact
{{business_impact}}

## Symptoms
{{symptoms}}

## Timeline
{{timeline}}

## Troubleshooting Performed
{{troubleshooting_performed}}

## Expected Behavior
{{expected_behavior}}

## Actual Behavior
{{actual_behavior}}

## Reproduction Steps
{{reproduction_steps}}

## Relevant Context
{{relevant_context}}

## Open Questions
{{open_questions}}

## Requested Help
{{requested_help}}

## Next Action
{{next_action}}
""",
    "troubleshooting_summary.md": """# Troubleshooting Summary: {{title}}

## Account
{{account_name}}

## Issue
{{issue_summary}}

## Environment / Configuration
{{environment}}

## Findings
{{findings}}

## Actions Taken
{{actions_taken}}

## Remaining Questions
{{remaining_questions}}

## Next Action
{{next_action}}
""",
    "meeting_agenda.md": """# Meeting Agenda: {{title}}

## Account
{{account_name}}

## Meeting Goal
{{meeting_goal}}

## Attendees
{{attendees}}

## Agenda
1. {{agenda_item_1}}
2. {{agenda_item_2}}
3. {{agenda_item_3}}

## Open Items To Cover
{{open_items}}

## Desired Outcomes
{{desired_outcomes}}
""",
    "meeting_recap.md": """# Meeting Recap: {{title}}

## What We Discussed
{{discussion_summary}}

## Decisions / Outcomes
{{decisions}}

## Next Steps
{{next_steps}}

## Follow-Up Tasks
{{follow_up_tasks}}
""",
    "research_summary.md": """# Research Summary: {{title}}

## Question
{{research_question}}

## Sources Reviewed
{{sources}}

## Findings
{{findings}}

## Interpretation
{{interpretation}}

## Recommendation
{{recommendation}}

## Open Questions
{{open_questions}}
""",
    "support_handoff.md": """# Support Handoff: {{title}}

## Account
{{account_name}}

## Customer Issue
{{issue_summary}}

## Business Impact
{{business_impact}}

## Troubleshooting Completed
{{troubleshooting_completed}}

## Evidence / Artifacts
{{evidence}}

## Requested Support Action
{{requested_action}}

## Customer Expectations
{{customer_expectations}}
""",
    "executive_summary.md": """# Executive Summary: {{title}}

## Account
{{account_name}}

## Executive Summary
{{summary}}

## Business Impact
{{business_impact}}

## Current Status
{{current_status}}

## Risks
{{risks}}

## Next Actions
{{next_actions}}
""",
    "course_usage_report.md": """# Course Usage Report: {{title}}

## Account
{{account_name}}

## Usage Summary
{{usage_summary}}

## Active Users
{{active_users}}

## Course Engagement
{{course_engagement}}

## Status Breakdown
{{status_breakdown}}

## Recommended Follow-Up
{{recommended_follow_up}}
""",
    "asset_metadata_report.md": """# Asset Metadata Report: {{title}}

## Account
{{account_name}}

## Asset Summary
{{asset_summary}}

## Metadata Completeness
{{metadata_completeness}}

## Missing / Incomplete Metadata
{{missing_metadata}}

## Update Recommendations
{{update_recommendations}}
""",
    "user_activity_report.md": """# User Activity Report: {{title}}

## Account
{{account_name}}

## Active Users
{{active_users}}

## Inactive Users
{{inactive_users}}

## Signals Used
{{signals_used}}

## Suggested Showpad Updates
{{suggested_updates}}
""",
    "showpad_update_export.md": """# Showpad Update Export: {{title}}

## Source Export
{{source_export}}

## Filters Applied
{{filters_applied}}

## Updates Applied
{{updates_applied}}

## Output CSV
{{output_csv}}

## Review Notes
{{review_notes}}
"""
}


def ensure_default_templates(template_dir: str | Path) -> list[Path]:
    path = Path(template_dir)
    path.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, content in DEFAULT_TEMPLATES.items():
        target = path / name
        if not target.exists():
            target.write_text(content, encoding="utf-8")
        written.append(target)
    return written
