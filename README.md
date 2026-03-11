# Vital City — Experiments Gallery

A prototype gallery page for [Vital City](https://www.vitalcitynyc.org/) showcasing creative urban data tools and maps built by independent developers and small teams.

## Files

### `index.html`
Self-contained gallery page prototype. Open in a browser to preview. All styles and JavaScript are inline — no build step required.

**For the Ghost developer:** This page is designed to be adapted into a Ghost page. The tool data lives in a JavaScript array at the bottom of the file, making it easy to update. The CSS uses custom properties that can be adjusted to match Vital City's exact brand fonts (swap `Source Serif 4` for `Gascogne`).

### `scanner/discover.py`
Monthly discovery script that scans GitHub, Hacker News, and Reddit for new urban data tools. Produces a ranked report of candidates.

```bash
# Install dependency
pip install requests

# Run scanner (outputs to terminal)
python scanner/discover.py

# Save a report
python scanner/discover.py --output report

# Optional: set GitHub token for higher rate limits
export GITHUB_TOKEN=your_token_here
python scanner/discover.py --output report --days 60
```

Reports are saved to `scanner/reports/`.

## Updating the Gallery

1. Run the scanner monthly: `python scanner/discover.py --output report`
2. Review the report and visit top candidates
3. Edit the `tools` array in `index.html` to add new tools
4. Set `archived: true` on tools you want to rotate out (they'll appear in the archive section)
