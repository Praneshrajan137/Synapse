/**
 * VisuallyHidden — content available to assistive tech but not painted.
 * Used for screen-reader labels and live-region announcements.
 */
export function VisuallyHidden({ children }: { children: React.ReactNode }) {
  return (
    <span
      style={{
        position: "absolute",
        width: 1,
        height: 1,
        padding: 0,
        margin: -1,
        overflow: "hidden",
        clip: "rect(0 0 0 0)",
        clipPath: "inset(50%)",
        whiteSpace: "nowrap",
        border: 0,
      }}
    >
      {children}
    </span>
  );
}
