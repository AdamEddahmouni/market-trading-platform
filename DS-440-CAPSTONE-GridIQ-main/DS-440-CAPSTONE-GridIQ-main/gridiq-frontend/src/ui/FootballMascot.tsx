type Props = { className?: string };

/** Simple football-with-face mascot for assistant chat bubbles. */
export function FootballMascot({ className = "" }: Props) {
  return (
    <svg
      className={className}
      width="40"
      height="40"
      viewBox="0 0 48 48"
      aria-hidden="true"
      focusable="false"
    >
      <ellipse cx="24" cy="24" rx="20" ry="13" fill="#6B3F22" stroke="#3D2414" strokeWidth="1.5" />
      <path d="M10 24h28" stroke="#E8E0D4" strokeWidth="2.2" strokeLinecap="round" />
      <path d="M16 19v10M24 17v14M32 19v10" stroke="#C9BDA8" strokeWidth="1.3" strokeLinecap="round" />
      <ellipse cx="19" cy="22" rx="2" ry="2.6" fill="#2D1A12" />
      <ellipse cx="29" cy="22" rx="2" ry="2.6" fill="#2D1A12" />
      <ellipse cx="19.6" cy="21.2" rx="0.6" ry="0.7" fill="#F5F0E6" />
      <ellipse cx="29.6" cy="21.2" rx="0.6" ry="0.7" fill="#F5F0E6" />
      <path
        d="M18 29c2 2 10 2 12 0"
        stroke="#2D1A12"
        strokeWidth="1.2"
        strokeLinecap="round"
        fill="none"
      />
    </svg>
  );
}
