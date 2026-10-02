Scrollbars, headed vs headless Chrome, and the geometry self-check
  The page does its arithmetic with layout geometry: hidden measuring elements whose widths encode numbers are read back
  through CSS scroll-driven animations, and one such element was decoded with the assumption that its scrolling box is
  exactly 524,288 px wide. A classic, space-taking scrollbar (macOS with "Show scroll bars: Always" or with a mouse
  attached, Windows, most Linux desktops) makes that box 15–17 px narrower, which shifted every read-back token id
  above ≈9,300 by +1 — the model then continued from the wrong word ("House ofEARTH" instead of "House of
  Representatives"). Headless Chrome, and Chrome started with --hide-scrollbars, never showed it; overlay scrollbars
  (macOS default with a trackpad only) take no space and are also unaffected. Since v6 the measuring box declares
  scrollbar-width:none (Chrome 121+), so the scrollbar policy of the OS no longer matters, and the page now
  self-checks the mechanism: a constant of known value is read back the same way before every token and each fed-back
  id is compared with the exact winner; if either check fails the run is HELD (no token appears) and a red panel
  "Geometry self-check failed" is shown instead of wrong text. If you see that panel: use Chrome/Edge 121 or newer
  (139+ is required anyway), do not run with a browser "minimum font size" set, keep the window at 100 % zoom
  if in doubt, then press Reset.
