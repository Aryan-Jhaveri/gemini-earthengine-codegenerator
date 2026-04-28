"""
Validator Agent — validates generated Earth Engine JavaScript code.

Validation strategy (deterministic first, LLM fallback):
  1. Parse the script for ee.ImageCollection(id) / ee.Image(id) calls and verify
     the dataset IDs exist in the STAC index.
  2. Check band names referenced in the script against the STAC index for those
     datasets.
  3. If deterministic checks pass (or index is unavailable), optionally run an
     LLM-based review via llm.stream_completion("validator", ...) with
     gemini/gemini-2.5-flash.

Streams validation status to the thought log and returns a structured result
consumed by the orchestrator's retry loop.
"""

import re
from typing import Optional

from .memory import shared_memory, AgentType
from .tools.stac_tools import get_dataset_schema


# Regex patterns for EE JS dataset ID references
_COLLECTION_RE = re.compile(r"""ee\.ImageCollection\s*\(\s*['"]([^'"]+)['"]\s*\)""")
_IMAGE_RE = re.compile(r"""ee\.Image\s*\(\s*['"]([^'"]+)['"]\s*\)""")
# Band references in .select(['B4', 'B8']) or .select('B4')
_SELECT_RE = re.compile(r"""\.select\s*\(\s*(?:\[([^\]]+)\]|(['"][^'"]+['"]))\s*\)""")


class ValidatorAgent:
    """
    Validates generated EE JavaScript before it reaches the user.

    Uses the STAC index for deterministic dataset ID and band name checks,
    then falls back to an LLM review for subtler issues.
    """

    def _stream(self, content: str) -> None:
        shared_memory.add_thought(AgentType.SYNTHESIZER, f"[Validator] {content}")

    def _extract_dataset_ids(self, code: str) -> list[str]:
        ids = _COLLECTION_RE.findall(code) + _IMAGE_RE.findall(code)
        # Filter out obvious non-dataset strings (short, no slash)
        return [i for i in ids if "/" in i or len(i) > 10]

    def _extract_band_names(self, code: str) -> list[str]:
        bands: list[str] = []
        for match in _SELECT_RE.finditer(code):
            array_content = match.group(1)  # inside [...]
            single = match.group(2)         # single quoted band
            if array_content:
                # Extract quoted strings from the array
                bands.extend(re.findall(r"""['"]([^'"]+)['"]""", array_content))
            elif single:
                bands.extend(re.findall(r"""['"]([^'"]+)['"]""", single))
        return bands

    def _check_dataset_ids(self, dataset_ids: list[str]) -> list[str]:
        """Return error messages for unrecognised dataset IDs."""
        errors = []
        for ds_id in dataset_ids:
            try:
                get_dataset_schema(ds_id)
            except ValueError as exc:
                errors.append(str(exc))
            except Exception:
                pass  # index unavailable — skip deterministic check
        return errors

    def _check_band_names(self, code: str, dataset_ids: list[str]) -> list[str]:
        """Return error messages for band names not present in any dataset schema."""
        if not dataset_ids:
            return []

        # Collect valid band names from all referenced datasets
        valid_bands: set[str] = set()
        for ds_id in dataset_ids:
            try:
                schema = get_dataset_schema(ds_id)
                valid_bands.update(b["name"] for b in schema.get("bands", []))
            except Exception:
                return []  # index unavailable — skip check

        if not valid_bands:
            return []

        referenced_bands = self._extract_band_names(code)
        errors = []
        for band in referenced_bands:
            if band not in valid_bands:
                errors.append(
                    f"Band '{band}' not found in any referenced dataset "
                    f"(valid bands: {sorted(valid_bands)[:10]}...)"
                )
        return errors

    async def validate(self, code: str) -> dict:
        """
        Validate EE JavaScript code.

        Returns:
            {
                "valid": bool,
                "errors": [str],      # blocking issues
                "suggestions": [str], # non-blocking improvements
            }
        """
        self._stream("🔍 Starting validation...")
        errors: list[str] = []
        suggestions: list[str] = []

        # --- Deterministic checks ---
        dataset_ids = self._extract_dataset_ids(code)
        if dataset_ids:
            self._stream(f"📦 Found dataset references: {dataset_ids}")
            id_errors = self._check_dataset_ids(dataset_ids)
            errors.extend(id_errors)

            band_errors = self._check_band_names(code, dataset_ids)
            errors.extend(band_errors)
        else:
            suggestions.append(
                "No ee.ImageCollection() or ee.Image() calls detected — "
                "make sure the script loads a dataset."
            )

        # --- Basic structural checks ---
        if "Map.addLayer" not in code:
            suggestions.append("Script does not call Map.addLayer() — no visualization will appear.")
        if "var " not in code and "let " not in code and "const " not in code:
            suggestions.append("No variable declarations found — script may be empty or malformed.")

        # --- LLM-based review (only when no blocking errors already found) ---
        if not errors:
            llm_errors, llm_suggestions = await self._llm_review(code, dataset_ids)
            errors.extend(llm_errors)
            suggestions.extend(llm_suggestions)

        valid = len(errors) == 0
        if valid:
            self._stream("✅ Code validated — no errors found")
        else:
            for err in errors:
                self._stream(f"❌ Error: {err}")

        for sug in suggestions:
            self._stream(f"💡 Suggestion: {sug}")

        return {"valid": valid, "errors": errors, "suggestions": suggestions}

    async def _llm_review(self, code: str, dataset_ids: list[str]) -> tuple[list[str], list[str]]:
        """Run a quick LLM review for subtle issues. Returns (errors, suggestions)."""
        from .llm import stream_completion

        prompt = f"""You are a Google Earth Engine code reviewer. Review this EE JavaScript for:
1. Deprecated API calls (e.g. ee.algorithms, old ImageCollection.map syntax)
2. Missing cloud masking when using optical imagery
3. Division-by-zero risks in index calculations
4. Incorrect date filter syntax

Code to review:
```javascript
{code[:3000]}
```

Datasets referenced: {dataset_ids}

Respond with a JSON object:
{{"errors": ["...blocking issue..."], "suggestions": ["...improvement..."]}}

Only include real issues. Respond with empty arrays if code looks correct."""

        messages = [{"role": "user", "content": prompt}]
        raw = ""
        try:
            async for event in stream_completion("validator", messages):
                if event["kind"] == "text":
                    raw += event["content"]

            # Parse JSON from response
            match = re.search(r'\{[^{}]*"errors"[^{}]*\}', raw, re.DOTALL)
            if match:
                import json
                result = json.loads(match.group())
                return result.get("errors", []), result.get("suggestions", [])
        except Exception as exc:
            self._stream(f"⚠️ LLM review failed: {exc}")
        return [], []


# Singleton
validator_agent = ValidatorAgent()
