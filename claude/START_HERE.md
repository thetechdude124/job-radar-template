# Start here (no coding needed - Claude does it with you)

This sets up your own **Job Radar**: a free tool that automatically finds
internships/jobs matching you every hour and drops them into a Google Sheet you
just open and apply from. You'll use **Claude** (your subscription) to do the
whole thing with you - no experience required. Takes ~10-15 minutes.

## How to use Claude for this

**Easiest (recommended):**
1. Go to [claude.ai](https://claude.ai) and start a **new chat**.
2. Open the file **`claude/ASSISTANT.md`** in this project, select all of it, and
   **copy** it.
3. **Paste** it into the Claude chat, then send this message right after:
   > Help me set up Job Radar, step by step. I'm not technical. Start by asking
   > me what kind of roles I want.
4. Follow along - Claude will ask a few questions, then guide you one step at a
   time. If anything errors, paste the error back to Claude and it'll help.

**Even smoother (if you use Claude a lot):** create a new **Project** in Claude,
paste the contents of `claude/ASSISTANT.md` into the project's custom
instructions, then chat inside that project.

## What Claude will help you pick
- Your field and the roles you want (software, quant, AI research, **product
  management**, **mechanical/hardware engineering**, career fairs, ...).
- Internships vs. full-time.
- Locations (US + Remote by default).
- Dream companies to pin to the top.

## What you'll end up with
A Google Sheet that fills itself every hour with matching roles. You just mark
the `Status` column as you apply. That's it.

> Prefer a written guide instead of Claude? See [../SETUP.md](../SETUP.md).
