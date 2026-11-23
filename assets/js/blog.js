/* Site behaviour that the theme doesn't provide. Loaded with `defer`. */
(function () {
  "use strict";

  /* Keep a scrolled-to element visible inside a scrollable panel. */
  function keepVisible(el, box) {
    if (!el || !box || box.scrollHeight <= box.clientHeight + 1) return;
    var pad = 48;
    var b = box.getBoundingClientRect();
    var r = el.getBoundingClientRect();
    if (r.top < b.top + pad) box.scrollTop -= b.top + pad - r.top;
    else if (r.bottom > b.bottom - pad) box.scrollTop += r.bottom - (b.bottom - pad);
  }

  /* 1. Article panels (series map, table of contents): open on wide
        screens, folded on small ones. single.html sets the first state
        inline; this keeps it right when the window is resized. */
  var panels = document.querySelectorAll("details[data-open-from]");
  Array.prototype.forEach.call(panels, function (panel) {
    var mq = window.matchMedia("(min-width: " + panel.getAttribute("data-open-from") + "px)");
    var sync = function () {
      panel.open = mq.matches;
    };
    if (mq.addEventListener) mq.addEventListener("change", sync);
    var current = panel.querySelector('[aria-current="page"]');
    if (current) keepVisible(current, panel);
  });

  /* 2. Table of contents: highlight the section being read. */
  var toc = document.querySelector(".post-panel--toc .toc-nav");
  if (toc) {
    var linkById = {};
    Array.prototype.forEach.call(toc.querySelectorAll('a[href^="#"]'), function (a) {
      linkById[decodeURIComponent(a.getAttribute("href").slice(1))] = a;
    });
    var anchors = Array.prototype.filter.call(
      document.querySelectorAll(".article-content .anchor[id]"),
      function (el) {
        return linkById[el.id];
      }
    );
    var active = null;
    var queued = false;
    var update = function () {
      queued = false;
      var line = window.innerHeight * 0.3;
      var hit = null;
      for (var i = 0; i < anchors.length; i++) {
        if (anchors[i].getBoundingClientRect().top <= line) hit = anchors[i];
        else break;
      }
      var atEnd = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4;
      if (atEnd && anchors.length && anchors[anchors.length - 1].getBoundingClientRect().top < window.innerHeight) {
        hit = anchors[anchors.length - 1];
      }
      var link = hit ? linkById[hit.id] : null;
      if (link === active) return;
      if (active) {
        active.classList.remove("is-active");
        active.removeAttribute("aria-current");
      }
      active = link;
      if (link) {
        link.classList.add("is-active");
        link.setAttribute("aria-current", "location");
        keepVisible(link, toc.closest(".post-panel"));
      }
    };
    window.addEventListener(
      "scroll",
      function () {
        if (!queued) {
          queued = true;
          window.requestAnimationFrame(update);
        }
      },
      { passive: true }
    );
    window.addEventListener("hashchange", update);
    update();
  }

  /* 3. Re-draw Mermaid diagrams when the OS switches light/dark while the
        page is open (the theme only handles its own toggle button). */
  if (window.matchMedia && typeof window.updateMermaidTheme === "function") {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
      window.setTimeout(window.updateMermaidTheme, 0);
    });
  }

  /* 4. Glossary terms ([SELinux](term:selinux) in Markdown): the explanation
        appears in a card on hover or keyboard focus; a click or tap pins it
        until the reader clicks elsewhere or presses Escape. Keyboard Enter
        and Ctrl/Cmd-click keep the link to the glossary page. Explanations
        come from the hidden block rendered by blog/glossary-defs.html. */
  var termDefs = document.querySelector(".term-defs");
  if (termDefs && document.querySelector("a.term")) {
    var card = document.createElement("div");
    card.className = "term-card";
    card.hidden = true;
    document.body.appendChild(card);

    var current = null; // the term the card belongs to
    var pinned = false; // opened by click or tap: stays until dismissed
    var showTimer = 0;
    var hideTimer = 0;

    var make = function (tag, cls, text) {
      var el = document.createElement(tag);
      el.className = cls;
      if (text) el.textContent = text;
      return el;
    };

    var fill = function (term) {
      var def = document.getElementById("term-def-" + term.getAttribute("data-term"));
      if (!def) return false;
      var text = make("div", "term-card__text");
      text.innerHTML = def.innerHTML;
      card.replaceChildren(make("div", "term-card__title", def.getAttribute("data-title")), text);
      var links = make("div", "term-card__links");
      var href = def.getAttribute("data-href");
      if (href) {
        var more = make("a", "term-card__more", termDefs.getAttribute("data-more"));
        more.href = href;
        links.appendChild(more);
      }
      var ext = def.getAttribute("data-link");
      if (ext) {
        var out = make("a", "term-card__ext", def.getAttribute("data-link-host") || ext);
        out.href = ext;
        out.target = "_blank";
        out.rel = "noopener noreferrer";
        links.appendChild(out);
      }
      if (links.firstChild) card.appendChild(links);
      return true;
    };

    /* Below the term, or above it when there is no room; always inside the
       viewport, with the arrow pointing at the term. */
    var place = function () {
      if (!current) return;
      var r = current.getBoundingClientRect();
      var edge = 12;
      var gap = 10;
      var w = card.offsetWidth;
      var h = card.offsetHeight;
      var vw = document.documentElement.clientWidth;
      var left = Math.max(edge, Math.min(r.left + r.width / 2 - w / 2, vw - edge - w));
      var below = r.bottom + gap + h <= window.innerHeight - edge || r.top - gap - h < edge;
      var top = below ? r.bottom + gap : r.top - gap - h;
      var base = { left: -window.scrollX, top: -window.scrollY };
      if (window.getComputedStyle(document.body).position !== "static") base = document.body.getBoundingClientRect();
      card.style.left = left - base.left + "px";
      card.style.top = top - base.top + "px";
      card.setAttribute("data-side", below ? "bottom" : "top");
      card.style.setProperty("--arrow-x", Math.max(14, Math.min(r.left + r.width / 2 - left, w - 14)) + "px");
    };

    var open = function (term, pin) {
      window.clearTimeout(showTimer);
      window.clearTimeout(hideTimer);
      if (term !== current) {
        if (!fill(term)) return;
        if (current) current.classList.remove("is-active");
        current = term;
        pinned = false;
      }
      if (pin) pinned = true;
      current.classList.add("is-active");
      card.hidden = false;
      // place() measures the card, so it is laid out (still transparent)
      // before .is-visible fades it in.
      place();
      card.classList.add("is-visible");
    };

    var close = function () {
      window.clearTimeout(showTimer);
      window.clearTimeout(hideTimer);
      if (!current) return;
      current.classList.remove("is-active");
      current = null;
      pinned = false;
      card.classList.remove("is-visible");
      card.hidden = true;
    };

    var termOf = function (el) {
      return el && el.closest ? el.closest("a.term") : null;
    };

    var focusVisible = function (el) {
      try {
        return el.matches(":focus-visible");
      } catch (err) {
        return true;
      }
    };

    // Mouse and pen: show after a short pause, hide when the pointer leaves
    // both the term and the card (the card can be hovered to click its links).
    document.addEventListener("pointerover", function (e) {
      if (e.pointerType === "touch") return;
      var term = termOf(e.target);
      if (term) {
        window.clearTimeout(hideTimer);
        if (term === current || pinned) return;
        window.clearTimeout(showTimer);
        showTimer = window.setTimeout(function () {
          open(term, false);
        }, current ? 0 : 250);
      } else if (card.contains(e.target)) {
        window.clearTimeout(hideTimer);
      }
    });

    document.addEventListener("pointerout", function (e) {
      if (e.pointerType === "touch") return;
      var from = termOf(e.target) || (card.contains(e.target) ? card : null);
      var to = e.relatedTarget;
      if (!from || (to && (from.contains(to) || card.contains(to) || (current && current.contains(to))))) return;
      window.clearTimeout(showTimer);
      if (current && !pinned) hideTimer = window.setTimeout(close, 300);
    });

    // Keyboard: Tab to a term shows its card.
    document.addEventListener("focusin", function (e) {
      var term = termOf(e.target);
      if (term && !pinned && focusVisible(term)) open(term, false);
    });

    document.addEventListener("focusout", function (e) {
      if (current && !pinned && termOf(e.target) === current) close();
    });

    // Click or tap: pin the card (again: close it). Anywhere else: close.
    document.addEventListener("click", function (e) {
      var term = termOf(e.target);
      if (term) {
        if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.detail === 0) return;
        e.preventDefault();
        if (term === current && pinned) close();
        else open(term, true);
      } else if (current && !card.contains(e.target)) {
        close();
      }
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && current) close();
    });

    window.addEventListener("resize", place);
    document.addEventListener(
      "scroll",
      function () {
        if (current) window.requestAnimationFrame(place);
      },
      { capture: true, passive: true }
    );
  }

  /* Email links from the theme's {{< email >}} shortcode without text: show
     the address, which is only in the page base64-encoded (against harvesters). */
  Array.prototype.forEach.call(document.querySelectorAll(".email-link[data-email]"), function (a) {
    if (!a.children.length && !a.textContent.trim()) a.textContent = atob(a.getAttribute("data-email")).replace(/^mailto:/, "");
  });

  /* 5. Sticky header: slides away while scrolling down, comes back on any
        scroll up. Sets html.header-hidden; custom.css moves the header and
        the sticky sidebars. Stays while the mobile menu is open. */
  var header = document.querySelector("body > header");
  if (header) {
    var menuToggle = document.getElementById("mobile-menu-toggle");
    var lastY = window.scrollY;
    window.addEventListener(
      "scroll",
      function () {
        var y = window.scrollY;
        if (Math.abs(y - lastY) < 8) return; // ignore jitter (touch, overscroll bounce)
        var hide = y > lastY && y > header.offsetHeight * 2 && !(menuToggle && menuToggle.checked);
        document.documentElement.classList.toggle("header-hidden", hide);
        lastY = y;
      },
      { passive: true }
    );
  }
})();
