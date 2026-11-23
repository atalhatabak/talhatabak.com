/* Overrides themes/blowfish/assets/js/mermaid.js
 * Same entry points (called by the theme's appearance.js), but diagrams
 * use the site font and the colour scheme in both light and dark mode. */
function css(name) {
  return "rgb(" + getComputedStyle(document.documentElement).getPropertyValue(name).trim() + ")";
}

var MERMAID_FONT = '"Inter Variable", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';

function initMermaidLight() {
  mermaid.initialize({
    theme: "base",
    fontFamily: MERMAID_FONT,
    themeVariables: {
      darkMode: false,
      fontFamily: MERMAID_FONT,
      fontSize: "15px",
      background: css("--color-neutral"),
      primaryColor: css("--color-primary-50"),
      primaryTextColor: css("--color-neutral-800"),
      primaryBorderColor: css("--color-primary-300"),
      secondaryColor: css("--color-secondary-50"),
      secondaryTextColor: css("--color-neutral-800"),
      secondaryBorderColor: css("--color-secondary-300"),
      tertiaryColor: css("--color-neutral-50"),
      tertiaryTextColor: css("--color-neutral-800"),
      tertiaryBorderColor: css("--color-neutral-300"),
      lineColor: css("--color-neutral-500"),
      textColor: css("--color-neutral-700"),
      clusterBkg: css("--color-neutral-50"),
      clusterBorder: css("--color-neutral-300"),
      edgeLabelBackground: css("--color-neutral"),
      noteBkgColor: css("--color-secondary-50"),
      noteBorderColor: css("--color-secondary-300"),
      noteTextColor: css("--color-neutral-800"),
      actorBkg: css("--color-primary-50"),
      actorBorder: css("--color-primary-300"),
      actorTextColor: css("--color-neutral-800"),
      signalColor: css("--color-neutral-600"),
      signalTextColor: css("--color-neutral-800"),
      labelBoxBkgColor: css("--color-neutral-50"),
      labelBoxBorderColor: css("--color-neutral-300"),
      activationBkgColor: css("--color-primary-100"),
      activationBorderColor: css("--color-primary-400"),
    },
  });
}

function initMermaidDark() {
  mermaid.initialize({
    theme: "base",
    fontFamily: MERMAID_FONT,
    themeVariables: {
      darkMode: true,
      fontFamily: MERMAID_FONT,
      fontSize: "15px",
      background: css("--color-neutral-800"),
      primaryColor: css("--color-neutral-700"),
      primaryTextColor: css("--color-neutral-100"),
      primaryBorderColor: css("--color-primary-400"),
      secondaryColor: css("--color-neutral-700"),
      secondaryTextColor: css("--color-neutral-100"),
      secondaryBorderColor: css("--color-secondary-400"),
      tertiaryColor: css("--color-neutral-800"),
      tertiaryTextColor: css("--color-neutral-100"),
      tertiaryBorderColor: css("--color-neutral-600"),
      lineColor: css("--color-neutral-400"),
      textColor: css("--color-neutral-200"),
      mainBkg: css("--color-neutral-700"),
      nodeBorder: css("--color-primary-400"),
      clusterBkg: css("--color-neutral-800"),
      clusterBorder: css("--color-neutral-600"),
      titleColor: css("--color-neutral-100"),
      edgeLabelBackground: css("--color-neutral-800"),
      noteBkgColor: css("--color-neutral-700"),
      noteBorderColor: css("--color-secondary-400"),
      noteTextColor: css("--color-neutral-100"),
      actorBkg: css("--color-neutral-700"),
      actorBorder: css("--color-primary-400"),
      actorTextColor: css("--color-neutral-100"),
      actorLineColor: css("--color-neutral-500"),
      signalColor: css("--color-neutral-300"),
      signalTextColor: css("--color-neutral-100"),
      labelBoxBkgColor: css("--color-neutral-700"),
      labelBoxBorderColor: css("--color-neutral-500"),
      labelTextColor: css("--color-neutral-100"),
      loopTextColor: css("--color-neutral-200"),
      activationBkgColor: css("--color-neutral-600"),
      activationBorderColor: css("--color-primary-400"),
      sequenceNumberColor: css("--color-neutral-900"),
    },
  });
}
