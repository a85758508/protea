"""Skill tool — let the LLM start a crystallized skill by name.

Pure stdlib.
"""

from __future__ import annotations

import logging
import time

from ring1.tool_registry import Tool

log = logging.getLogger("protea.tools.skill")


def make_run_skill_tool(skill_store, skill_runner) -> Tool:
    """Create a Tool that starts a stored skill by name."""

    def _exec_run_skill(inp: dict) -> str:
        skill_name = inp["skill_name"]

        # 1. Look up the skill in the store.
        skill = skill_store.get_by_name(skill_name)
        if skill is None:
            return f"Error: skill '{skill_name}' not found."

        source_code = skill.get("source_code", "")
        if not source_code:
            return f"Error: skill '{skill_name}' has no source code."

        # 2. If the same skill is already running, return its current status.
        if skill_runner.is_running():
            info = skill_runner.get_info()
            if info and info.get("skill_name") == skill_name:
                output = skill_runner.get_output(max_lines=30)
                # Re-detect port in case it appeared after startup.
                parts = [f"Skill '{skill_name}' is already running (PID {info['pid']})."]
                if info.get("port"):
                    parts.append(f"HTTP port: {info['port']}")
                    parts.append(f"Use web_fetch with http://localhost:{info['port']} to interact.")
                if output:
                    parts.append(f"\nRecent output:\n{output}")
                return "\n".join(parts)

            # Different skill running — stop it first.
            old_info = skill_runner.get_info()
            old_name = old_info["skill_name"] if old_info else "unknown"
            skill_runner.stop()
            log.info("Stopped previous skill '%s' to start '%s'", old_name, skill_name)

        # 3. Start the skill.
        try:
            pid, message = skill_runner.run(skill_name, source_code)
        except Exception as exc:
            return f"Error starting skill '{skill_name}': {exc}"

        # 4. Update usage count.
        try:
            skill_store.update_usage(skill_name)
        except Exception:
            pass  # non-critical

        # 5. Wait for initialization and port detection.
        time.sleep(3)

        # 6. Collect status.
        info = skill_runner.get_info()
        output = skill_runner.get_output(max_lines=30)

        parts = [f"Skill '{skill_name}' started (PID {pid})."]

        if info and info.get("port"):
            parts.append(f"HTTP port: {info['port']}")
            parts.append(f"Use web_fetch with http://localhost:{info['port']} to interact.")

        if not skill_runner.is_running():
            parts.append("WARNING: Process exited shortly after starting.")

        if output:
            parts.append(f"\nInitial output:\n{output}")

        return "\n".join(parts)

    return Tool(
        name="run_skill",
        description=(
            "Start a stored Protea skill by name. Skills are standalone programs "
            "crystallized from successful evolution. Returns status, output, and "
            "HTTP port if available. Use web_fetch to interact with the skill's "
            "API after starting it."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "Name of the skill to start.",
                },
            },
            "required": ["skill_name"],
        },
        execute=_exec_run_skill,
    )
