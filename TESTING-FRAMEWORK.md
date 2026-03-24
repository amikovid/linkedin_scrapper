# LinkedIn Testing Framework

> **Note:** This document originates from a separate internal project (OpenEd content strategy) and is included here as the classification framework that drives the AI analysis. The variables, hypotheses, and status fields below belong to that project — this scraper uses the framework definitions to classify posts from *any* LinkedIn account, not just OpenEd's.

*Internal. Populated as we research and post. Goal: figure out what actually works for OpenEd's audience before we bake it into the skill.*

Last updated: 2026-03-23

---

## How to Use This

Each variable below has a hypothesis and a status. As we post, tag each post with which variable we're testing (one at a time). After 3+ data points on a variable, we can call a winner and lock it in. Status levels: `hypothesis` → `testing` → `confirmed` → `locked`.

Post log tracks the raw data. This doc tracks the conclusions.

---

## Variable 1: Hook Type

**The question:** Which opening pattern gets the most "see more" clicks and comments for OpenEd's audience?

Proxy signal: comment/like ratio (comments indicate actual engagement; likes are passive). Also look for comments that engage with the substance vs. generic "great post."

| Hook Type | Hypothesis | Status | Evidence so far |
|-----------|-----------|--------|----------------|
| Contradicting | Highest potential - breaks pattern, forces re-read. "Something shifted and nobody announced it." | `hypothesis` | — |
| Emotional / scene-first | Strong - specific moment draws reader into a story before they know it's about ed | `hypothesis` | — |
| Authority / social proof | Moderate - works when the person is recognizable; weaker for obscure researchers | `hypothesis` | — |
| Transformation (before/after) | Strong for parent audience - maps to their lived experience | `hypothesis` | — |
| Data / stat-first | Moderate - depends on stat being genuinely surprising, not just confirmatory | `hypothesis` | — |
| Analogy | Untested in existing vault - could be strong for simplifying abstract ed concepts | `hypothesis` | — |
| Polarizing / hot take | Risky for brand account - could alienate; worth one careful test | `hypothesis` | — |
| Question | Weakest hypothesis - question hooks often feel like setup; audience can predict the answer | `hypothesis` | — |

**Priority testing order:** Contradicting → Emotional/scene → Transformation → Data → Analogy

**Cross-niche pattern to watch for in creator research (Day 2):** The highest-performing posts in non-ed niches most often open with a big specific number (not a stat, just anything concrete - a count, dollar amount, time span) followed by the story behind it. This isn't a separate hook type - it's usually Contradicting or Data - but the number is what does the first-line work. When reviewing creators via PhantomBuster or manual browsing, note whether their top posts follow this pattern and what the number is anchoring.

---

## Variable 2: Content Body Type

**The question:** After the hook lands, what body structure keeps people reading and drives comments?

| Body Type | Description | Hypothesis | Status | Evidence |
|-----------|-------------|-----------|--------|---------|
| Story arc | Setup → complication → resolution. One person's journey. | Strong - the JFM dyslexia post, the treehouse post both use this | `hypothesis` | — |
| Data narrative | Surprising stat → interpretation → implication | Strong for credibility; weaker for emotional engagement | `hypothesis` | — |
| Contrarian reframe | State common belief → show why it's wrong/incomplete → offer better frame | High ceiling, higher risk | `hypothesis` | — |
| List / framework | 3-5 points with brief explanations | Easier to skim; lower comment depth | `hypothesis` | — |
| Quote + context | Person said X → here's what that means → implication | Depends entirely on the quote's strength | `hypothesis` | — |
| Observation chain | String of related observations building to one conclusion | Works in the school choice post; requires tight writing | `hypothesis` | — |

**Note on length:** SCOPE.md says 200-500 words optimal. The vault's best posts run 200-300. Don't pad to hit 500.

---

## Variable 3: CTA / Closing

**The question:** How should posts end to maximize meaningful engagement (comments > likes)?

| Closing Type | Example | Hypothesis | Status | Evidence |
|-------------|---------|-----------|--------|---------|
| Open question (specific) | "What changed that for your family?" | Good if question is genuinely interesting; bad if it's generic | `hypothesis` | — |
| Implication statement | "The loudest arguments are still happening. But the numbers underneath them have already moved." | Strong - leaves reader thinking without asking anything | `hypothesis` | — |
| Direct quote as closer | End with a guest's line that lands | Strong - transfers authority to a real person | `hypothesis` | — |
| Link drop (no CTA language) | "Full conversation on the OpenEd podcast." (no "check it out!") | Neutral - signals there's more without demanding action | `hypothesis` | — |
| Hard CTA | "Follow us for more / share this" | Weakest - signals the post is promotional | `hypothesis` | — |
| No close (just stop) | Post ends on the final insight, no wrap-up | Underused; can feel abrupt or feel intentionally sharp | `hypothesis` | — |

**Working hypothesis:** The implication statement and direct quote closer outperform explicit questions. The question closer only works when the question is so specific it prompts a real answer, not a nod.

---

## Variable 4: Person Featured

**The question:** Does featuring a recognizable person vs. an unknown person affect engagement?

| Featured person type | Hypothesis | Status | Evidence |
|---------------------|-----------|--------|---------|
| Well-known public figure (JFM, Peter Gray) | Higher initial reach if they engage or share; risk of riding coattails | `hypothesis` | — |
| Mid-tier ed influencer (Michael Horn, Derrell Bradford) | Good - credible in the ed space, likely to engage back | `hypothesis` | — |
| Unknown researcher / study | Lower virality; higher trust signal for data-savvy audience | `hypothesis` | — |
| OpenEd podcast guest (any) | Moderate - guest may share; audience may not know them | `hypothesis` | — |
| No person (OpenEd position statement) | Lowest hypothesis - brand accounts without a human anchor tend to underperform | `hypothesis` | — |

---

## Variable 5: Creative / Visual Direction

**The question:** Does a visual asset on LinkedIn (image, quote card, carousel) meaningfully change engagement vs. text-only?

*Note: LinkedIn text-only posts often outperform image posts because the algorithm treats images as "ad-like." But carousels are a different category. Worth testing.*

| Format | Hypothesis | Status | Evidence |
|--------|-----------|--------|---------|
| Text only | High hypothesis for comments; LinkedIn algorithm may favor | `hypothesis` | — |
| Quote card (single image) | Moderate - depends on quote strength and design quality | `hypothesis` | — |
| Carousel (multi-slide) | Potentially high - LinkedIn treats as document, pushes reach; but requires design effort | `hypothesis` | — |
| Podcast cover + text | Low - looks promotional | `hypothesis` | — |

---

## Variable 6: Posting Time / Frequency

**Lower priority - test last. Content quality matters more than timing for a small account.**

| Variable | Common advice | OpenEd hypothesis | Status |
|----------|--------------|------------------|--------|
| Day of week | Tue-Thu best | Probably true; Mon and Fri are lower-intent scroll days | `hypothesis` |
| Time of day | 7-9am or 12-1pm local | Unknown for OpenEd's audience (parents? educators? both have different schedules) | `hypothesis` |
| Frequency | 3-5x/week | 3x/week is sustainable and enough to build pattern | `hypothesis` |

---

## What We're NOT Testing (Per SCOPE.md)

- Hashtag count / combinations
- Posting time optimization matrices
- A/B split testing on the same content
- Any metric other than 48hr likes + 48hr comments from the post log

---

## Sources to Draw From (As They're Added)

| Source | Key variables it informs | Status |
|--------|-------------------------|--------|
| Paolo Trivellato - LinkedIn Psychology | Emotional triggers, hook psychology, lead magnet FOMO | Analyzed |
| Noorman - HOOKS.md | Hook taxonomy (10 types) | Analyzed |
| Noorman - STORYTELLING.md | Body type options (transformation, social hacking) | Analyzed |
| Content Hooks CSV | Additional hook templates | Analyzed |
| Charlie's existing posts (vault) | Real examples for hook + body + CTA patterns | Analyzed |
| Charlie's existing resources | TBD | Pending |
| Cody Schneider resources | TBD | Pending |
| Manual creator research (Day 2) | Hook type evidence from non-ed accounts | Pending |
| Actual post performance (sprint weeks 1-2) | All variables | Pending |
