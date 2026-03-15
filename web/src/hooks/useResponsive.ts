import { useEffect, useState } from "react";

interface ResponsiveState {
  isMobile: boolean;
  isTablet: boolean;
  isDesktop: boolean;
}

const MOBILE_QUERY = "(max-width: 767px)";
const TABLET_QUERY = "(min-width: 768px) and (max-width: 1023px)";
const DESKTOP_QUERY = "(min-width: 1024px)";

function getState(
  mobile: MediaQueryList,
  tablet: MediaQueryList,
  desktop: MediaQueryList,
): ResponsiveState {
  return {
    isMobile: mobile.matches,
    isTablet: tablet.matches,
    isDesktop: desktop.matches,
  };
}

export function useResponsive(): ResponsiveState {
  const [state, setState] = useState<ResponsiveState>(() => {
    const mobile = window.matchMedia(MOBILE_QUERY);
    const tablet = window.matchMedia(TABLET_QUERY);
    const desktop = window.matchMedia(DESKTOP_QUERY);
    return getState(mobile, tablet, desktop);
  });

  useEffect(() => {
    const mobile = window.matchMedia(MOBILE_QUERY);
    const tablet = window.matchMedia(TABLET_QUERY);
    const desktop = window.matchMedia(DESKTOP_QUERY);

    function update() {
      setState(getState(mobile, tablet, desktop));
    }

    mobile.addEventListener("change", update);
    tablet.addEventListener("change", update);
    desktop.addEventListener("change", update);

    return () => {
      mobile.removeEventListener("change", update);
      tablet.removeEventListener("change", update);
      desktop.removeEventListener("change", update);
    };
  }, []);

  return state;
}
