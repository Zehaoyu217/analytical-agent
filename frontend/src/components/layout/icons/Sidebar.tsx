import type { SVGProps } from "react";

interface SidebarIconProps extends SVGProps<SVGSVGElement> {
  size?: number;
}

export function SidebarIcon({ size = 16, ...rest }: SidebarIconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M9 3v18" />
    </svg>
  );
}

export function SidebarOnIcon({ size = 16, ...rest }: SidebarIconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <rect
        x="3"
        y="3"
        width="6"
        height="18"
        rx="2"
        fill="currentColor"
        stroke="none"
      />
    </svg>
  );
}
