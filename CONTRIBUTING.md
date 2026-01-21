# PatchRaptor - Contributing

## Support & Community

**Do you have a question?**  
Please do **not** open a GitHub Issue for general support or setup questions.
*   Join our **[https://discord.gg/dS3xKYUK96](#)** for real-time support.
*   The community is active and can help you debug config issues much faster than a GitHub thread.

**Structure:**
*   **Discord:** Setup help, "Is this a bug?", General questions.
*   **GitHub Issues:** Verified bugs, Feature requests, Code contributions.

## Reporting Bugs

If you have found a verified bug (after checking with Discord):
1.  **Search** the existing Issues to avoid duplicates.
2.  **Open a new Issue** and include:
    *   **Logs:** Relevant snippets from `logs/system.log` (Redact your tokens!).
    *   **Context:** What OS/Version are you running?
    *   **Steps to Reproduce:** A clear list of steps to make the bug happen.

## Pull Requests

We welcome code contributions! To ensure a smooth merge:

1.  **Fork** the repository and create your branch from `main`.
2.  **Environment Setup:**
    *   Run `install_requirements.bat` and select **Option 2 (Development)** to get the testing tools.
3.  **Make your changes.** 
4.  **Verify Code:**
    *   You **MUST** run `verify.bat` locally before submitting.
    *   This runs our Smoke Tests and Unit Tests.
    *   PRs that fail the automated tests will not be merged.
5.  **Submit the PR:**
    *   Keep descriptions short and clear.
    *   Link to any relevant Issues.

## Structure & Style
*   **Safety First:** PatchRaptor is used on production servers. Avoid dangerous file operations without safety nets (like `_before_restore` backups).
*   **No Hardcoded Paths:** Always use `os.path.join` and relative paths.
*   **Type Hinting:** Please use Python type hints in function signatures where possible.

Thanks for helping make PatchRaptor better! 🦖 
