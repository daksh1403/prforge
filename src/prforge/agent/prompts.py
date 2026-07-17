"""Prompt templates for each agent node."""

from __future__ import annotations

from prforge.utils import format_files, truncate

LOCALIZE_SYSTEM = (
    "You are an expert software engineer triaging a GitHub issue. "
    "Given the issue and a repository map, identify the files most likely "
    "relevant to fixing it. Respond with ONLY a JSON array of relative paths "
    "that exist in the map. Prefer 2-6 files."
)

PLAN_SYSTEM = (
    "You are a senior software engineer fixing a GitHub issue. "
    "Read the issue, the repository map, and the relevant file contents. "
    "Write a concise, concrete step-by-step plan: which files to change and "
    "exactly what to change in each. Do NOT write the code yet."
)

EDIT_SYSTEM = (
    "You are an expert software engineer. Implement the plan using Aider-style "
    "SEARCH/REPLACE blocks.\n\n"
    "Output ONLY blocks in this exact format (one per change, multiple allowed):\n\n"
    "path/to/file.py\n"
    "<<<<<<< SEARCH\n"
    "exact original lines from the file\n"
    "=======\n"
    "new lines\n"
    ">>>>>>> REPLACE\n\n"
    "Rules:\n"
    "- The SEARCH text MUST match the file EXACTLY, including whitespace and indentation.\n"
    "- Copy enough surrounding context (3-6 lines) so the match is unique.\n"
    "- To add code, include surrounding lines in SEARCH and add the new lines in REPLACE.\n"
    "- To delete code, put the lines in SEARCH and omit them from REPLACE.\n"
    "- Do NOT output anything except the SEARCH/REPLACE blocks."
)

PR_SYSTEM = (
    "You write clear, professional GitHub pull request descriptions. "
    "Be concise. Reference the issue with 'Closes #N'."
)


def localize_prompt(issue_title: str, issue_body: str, repo_map: str) -> str:
    return (
        f"Issue #{''}: {issue_title}\n\n{issue_body}\n\n"
        f"Repository map:\n{truncate(repo_map, 8000)}\n\n"
        "Return a JSON array of the most relevant file paths."
    )


def plan_prompt(issue_number: int, issue_title: str, issue_body: str,
                 repo_map: str, file_contents: dict[str, str]) -> str:
    return (
        f"GitHub issue #{issue_number}: {issue_title}\n\n{issue_body}\n\n"
        f"Repository map:\n{truncate(repo_map, 6000)}\n\n"
        f"Relevant file contents:\n{truncate(format_files(file_contents), 20000)}\n\n"
        "Write the implementation plan."
    )


def edit_prompt(plan: str, file_contents: dict[str, str], test_output: str | None) -> str:
    section = ""
    if test_output:
        section = (
            "\n\nThe previous attempt FAILED tests. Test output:\n"
            f"{truncate(test_output, 6000)}\n"
            "Fix the failing tests in your edits.\n"
        )
    return (
        f"Plan:\n{truncate(plan, 4000)}\n\n"
        f"Current file contents:\n{truncate(format_files(file_contents), 24000)}\n"
        f"{section}\n"
        "Output the SEARCH/REPLACE blocks now."
    )


def pr_prompt(issue_number: int, issue_title: str, plan: str, diff: str) -> str:
    return (
        f"Write a PR for issue #{issue_number}: {issue_title}\n\n"
        f"Plan was:\n{truncate(plan, 2000)}\n\n"
        f"Diff:\n{truncate(diff, 8000)}\n\n"
        "Respond in EXACTLY this format:\n"
        "TITLE: <one-line title>\n"
        "BODY:\n<markdown body with bullet points, ending with 'Closes #{n}'>"
    )
