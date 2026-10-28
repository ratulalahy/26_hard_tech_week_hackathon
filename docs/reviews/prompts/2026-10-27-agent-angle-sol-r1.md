# Strategy question: an "AI agent" component for GridPilot (Sol, r1)

The owner asks: does this project need an AI-agent element, and if so, what kind? Give your own independent view.

**Context.** Read these files:
- `AGENTS.md`;
- `docs/brief.md`;
- `docs/pitch/narrative.md`, `docs/pitch/qa.md` and `docs/pitch/deck-outline.md`;
- `docs/decisions.md`, D-050 to D-074;
- `results/metrics.json` (validation), and `results/test/metrics.json` with `results/test/extras.json` (the sealed test year, opened once at 19:23 MT today).

The bounty is Torus's "Energy × AI infrastructure", judged on creativity, clarity of insight and execution, on Wed 2026-10-28 at 17:00 MT. It is a 4:30 demo plus Q&A, with a solo presenter.

**Facts:**
- **The router's policies contain no AI agent.** They are deterministic: a static clean-region ranking (S), climatology (K), a weekly forecast (W), a gradient-boosted forecast (L), and a hindsight benchmark (H). They run in a job simulator.
- **The test-year result:** S cuts attributed CO₂ by 22.3% [17.3, 26.4] against running everything in Utah. Forecast-based policies do not beat S.
- **The build process did use AI agents:** a lead Claude agent with builder subagents, a fresh independent reviewer for each piece, and Codex gates. All of it ran under a sealed-test protocol, with a decision log and rebuilds from raw data.
  - Tonight the reviewers caught a wrong test cutoff, overstated forecast skill, a storage schedule that missed the rush hour, and an unregistered price-node choice. All were fixed before the seal opened.
- **The test year is now closed.** Any new experiment would be unregistered.

**The lead's proposal (critique it; don't assume it is right):**
- (1) Add about 20 s and one slide to the pitch on the agent-built, independently reviewed, sealed-test process.
- (2) Optionally, an offline, pre-generated plain-language explanation for each routing decision on a "Monitor" page, labelled as an explanation, not a decision-maker.
- (3) Add no agent to the experiment itself.

**Answer each:**
1. Would judges for this bounty expect or reward an agent element? Would its absence hurt the "AI" half of "Energy × AI"?
2. Is (1) persuasive, or does it distract or look like a gimmick? If you keep it, what exact wording would you use?
3. Is (2) worth building tonight compared with the other remaining work: dashboard test view, nav shell, deck, results audit and rehearsals?
4. Is there a better, honest agent angle we are missing that fits the time left (about 20 h) and does not touch the closed test year? For example, an agentic operator workflow demo built on the frozen outputs.
5. Are there risks of overclaiming in any of these?

Report every finding with severity and confidence, then the verdict line.
