---
name: design-md
description: "Use this skill when the user wants a page, component, landing page, dashboard, or app UI to match a specific brand or website aesthetic; when they mention DESIGN.md, getdesign, or awesome-design-md; or when the task is to turn a design language into working frontend code. First look for a project-root DESIGN.md and treat it as the visual source of truth. If no DESIGN.md exists but the user references a known product style such as Vercel, Linear, Notion, Stripe, Supabase, Claude, or Raycast, use the DESIGN.md workflow to import or draft a style brief before coding. Do not use this skill for backend-only work or generic styling with no design direction."
metadata: { "builtin_skill_version": "1.0" }
---

# DESIGN.md-driven UI work

Use this skill to keep frontend work visually consistent when the user wants a UI to feel like a known product or when a project already includes a `DESIGN.md`.

## Core rule

Treat `DESIGN.md` as the visual equivalent of `AGENTS.md`:

- `AGENTS.md` explains how to work in the codebase
- `DESIGN.md` explains how the UI should look and feel

If both exist, follow both.

## When this skill should trigger

- The user mentions `DESIGN.md`, `getdesign`, or `awesome-design-md`
- The user says "make it look like Vercel / Linear / Notion / Stripe / Supabase / Claude / Raycast" or similar
- The user wants a UI restyle, landing page, dashboard, marketing page, or component library with a specific visual direction
- The project already has a root-level `DESIGN.md`

## Workflow

### 1. Find the design source

Start in this order:

1. Check whether the project root already contains `DESIGN.md`
2. If it exists, read it before making UI changes
3. If it does not exist and the user named a known product/site style, read `references/awesome-design-md.md`
4. If network and package install are available, you may import a public design brief with:

```bash
npx getdesign@latest add <slug>
```

Run it from the project root so the resulting `DESIGN.md` lands in the right place.

If import is unavailable, create a concise local `DESIGN.md` or an equivalent implementation brief yourself before coding.

### 2. Normalize the design into implementation tokens

Translate the design source into concrete implementation rules:

- Visual theme and atmosphere
- Color roles and CSS variables
- Typography stack, hierarchy, weights, tracking
- Component patterns: buttons, cards, inputs, nav, tables
- Layout rules: spacing scale, container widths, grid rhythm
- Depth: borders, shadows, glass, surface hierarchy
- Motion: entrance, hover, and transition style
- Responsive rules and mobile compromises
- Do-not-do rules that prevent generic or off-brand UI

When building in code, reflect these decisions in theme tokens, utility classes, component props, and reusable primitives instead of sprinkling one-off styles everywhere.

### 3. Build with one clear visual direction

Avoid averaging multiple aesthetics together. Pick one direction and carry it through:

- Keep color, radius, spacing, and shadow systems consistent
- Match the tone of typography, not just the colors
- Style loading, empty, hover, focus, error, and disabled states too
- Preserve existing product behavior unless the user asked for UX changes
- Prefer intentional surfaces, gradients, and motion over flat boilerplate layouts

### 4. Validate before finishing

Before wrapping up, sanity-check:

- Does the page still feel like the chosen reference without copying it literally?
- Are repeated components visually consistent with each other?
- Is the mobile layout still coherent?
- Did you avoid the default "AI-looking" purple gradient / generic SaaS style when the reference suggests something else?

## If no DESIGN.md exists yet

For design-led frontend requests, it is reasonable to create a lightweight `DESIGN.md` first. Keep it short and practical. A useful minimal file usually covers:

1. Atmosphere
2. Color palette and semantic roles
3. Typography
4. Component styling
5. Layout and spacing
6. Depth and borders/shadows
7. Motion
8. Responsive behavior
9. Do's and don'ts

## Reference file

Read `references/awesome-design-md.md` when you need:

- A quick refresher on the DESIGN.md concept
- Public inspiration slugs from the `awesome-design-md` collection
- Suggested prompt patterns for using imported design briefs
