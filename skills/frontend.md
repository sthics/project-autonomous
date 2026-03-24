# Frontend Development Best Practices

## Project Setup
- Use Next.js for full apps; plain React + Vite for simple SPAs.
- Tailwind CSS for styling (utility-first, minimal custom CSS).
- TypeScript preferred for anything beyond a landing page.

## Component Architecture
- Keep components small and focused (under 100 lines).
- Separate container (logic) from presentational (UI) components.
- Use composition over prop drilling — lift state to nearest common parent.
- Co-locate component, styles, and tests in the same directory.

## Styling
- Use Tailwind utility classes directly in JSX.
- Extract repeated patterns into component abstractions, not CSS classes.
- Design mobile-first, then add responsive breakpoints (`sm:`, `md:`, `lg:`).
- Use CSS variables for theme colors; define in `tailwind.config.js`.

## Forms
- Use controlled components with React state or react-hook-form.
- Validate on blur and on submit; show inline error messages.
- Disable submit button while loading; show spinner.
- Always include accessible labels and aria attributes.

## Performance
- Lazy-load routes and heavy components with `React.lazy` / `dynamic`.
- Optimize images: use `next/image` or compressed formats (WebP).
- Minimize bundle size: avoid large libraries for simple tasks.
- Use `useMemo`/`useCallback` only when you've measured a performance issue.

## Accessibility
- Use semantic HTML elements (`<nav>`, `<main>`, `<button>`, not `<div onClick>`).
- Ensure color contrast meets WCAG AA (4.5:1 for text).
- All interactive elements must be keyboard-navigable.
- Add `alt` text to all images.

## Landing Pages
- Clear value proposition above the fold.
- Single primary CTA per section.
- Social proof (testimonials, logos, stats) below the fold.
- Fast load time — target <2s on 3G.
