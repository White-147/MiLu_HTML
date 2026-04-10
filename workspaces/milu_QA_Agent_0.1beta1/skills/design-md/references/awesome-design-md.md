## DESIGN.md reference

This skill is based on the public idea described by VoltAgent's `awesome-design-md` collection:

- GitHub: `https://github.com/VoltAgent/awesome-design-md`
- Design catalog: `https://getdesign.md`

The core idea is simple:

- Put `DESIGN.md` in the project root
- Let the coding agent read it before UI work
- Use the file as the style source of truth for generated frontend code

## What a DESIGN.md usually captures

According to the public collection, a strong `DESIGN.md` usually covers:

1. Visual theme and atmosphere
2. Color palette and semantic roles
3. Typography rules
4. Component stylings
5. Layout principles
6. Depth and elevation
7. Do's and don'ts
8. Responsive behavior
9. Agent prompt guide

Use these sections as a checklist when importing, writing, or interpreting a design brief.

## Common inspiration slugs

These are useful examples when the user asks for a familiar product aesthetic:

| Style | Slug | Notes |
|------|------|------|
| Vercel | `vercel` | Black/white precision, Geist-like feel |
| Linear | `linear.app` | Minimal, precise, calm purple accent |
| Notion | `notion` | Warm minimalism, soft surfaces, editorial feel |
| Stripe | `stripe` | Elegant gradients, refined spacing, premium fintech tone |
| Supabase | `supabase` | Dark emerald, code-first developer aesthetic |
| Claude | `claude` | Warm editorial layout with terracotta accents |
| Raycast | `raycast` | Dark polished chrome with vivid gradient accents |
| Cursor | `cursor` | AI-native dark interface with sharp highlights |
| Framer | `framer` | Motion-forward, bold black/blue marketing style |
| Spotify | `spotify` | Dark surfaces with bold green emphasis |

## Importing a public DESIGN.md

If the environment allows package execution and the user wants a public inspiration, run from the project root:

```bash
npx getdesign@latest add <slug>
```

Example:

```bash
npx getdesign@latest add vercel
```

That should place a `DESIGN.md` in the project root. After that:

1. Read `DESIGN.md`
2. Extract tokens and rules
3. Build the UI against those rules

## When import is not possible

If network access, package download, or CLI execution is unavailable:

- Create a compact `DESIGN.md` locally
- Base it on the requested reference style and the visible product traits the user cares about
- Keep it implementation-oriented rather than writing brand history or fluffy prose

## Prompt patterns

These prompts are good mental templates for downstream UI work:

- "Use `DESIGN.md` as the visual source of truth and build the page to match it."
- "Keep the current information architecture, but restyle the UI so it follows `DESIGN.md`."
- "Create a landing page in the style described by `DESIGN.md`, including hero, feature grid, and CTA."
- "Extend the current component set without breaking the existing color, type, spacing, and surface rules from `DESIGN.md`."

## Practical guidance

- Prefer design consistency over squeezing in every trendy effect
- Reuse a small set of tokens repeatedly
- If the reference is sparse, infer carefully and keep the result coherent
- Match the reference's density and restraint, not just its accent color
