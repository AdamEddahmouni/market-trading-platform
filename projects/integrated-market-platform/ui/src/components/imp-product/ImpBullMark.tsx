type Props = {
  className?: string;
};

/** Stylized bull-head mark (board 03) — inline SVG, no external assets. */
export function ImpBullMark({ className }: Props) {
  return (
    <svg
      className={className}
      viewBox="0 0 48 48"
      width="40"
      height="40"
      role="img"
      aria-label="IMP"
    >
      <defs>
        <linearGradient id="imp-bull-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#FF8A00" />
          <stop offset="100%" stopColor="#FF6A00" />
        </linearGradient>
      </defs>
      <path
        fill="url(#imp-bull-grad)"
        d="M24 6c-2 0-4 1.5-5 3.5-3-1-6 0-7.5 2.5-2 2.8-1 7 2 9.5-1.5 2.5-2 5.5-1 8.5 1.5 5 6.5 8 11.5 7.5 5-.5 9-4.5 10-9.5.5-2.5 0-5-1.5-7 3-2.5 4-6.5 2.5-9.5C33 7 30 5.5 27 7 26 6 25 6 24 6zm-8 8c.5-1.5 2-2.5 3.5-2 1 .3 1.8 1.2 2 2.2-.8.5-1.5 1.2-2 2-.3-1-.5-1.5-1-2.2zm16 0c-.5-.7-.7-1.2-1-2.2-.5-.8-1.2-1.5-2-2 .2-1 1-1.9 2-2.2 1.5-.5 3 .5 3.5 2 .5 1.5 0 2.5-.5 4.2zM24 38c-4 0-7.5-2-9-5.5 2.5 1.5 5.5 2 9 1.5 3.5.5 6.5 0 9-1.5-1.5-4.5-5-9-5z"
      />
      <path
        fill="#1a1208"
        opacity="0.35"
        d="M18 22c1.2 1.5 3.8 2 6 1.5 2.2-.5 4-2 4.5-3.5"
      />
    </svg>
  );
}
