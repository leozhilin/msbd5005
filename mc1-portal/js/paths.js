/**
 * Resolve data and ../MC1 paths when the portal is hosted under a subpath (e.g. GitHub Pages /repo/mc1-portal/).
 */
(function (global) {
  var MARK = "/mc1-portal";
  var MARKS = "/mc1-portal/";

  function portalBasePath() {
    var p = location.pathname || "/";
    var a = p.indexOf(MARKS);
    if (a >= 0) {
      return p.substring(0, a + MARKS.length);
    }
    a = p.indexOf(MARK);
    if (a >= 0) {
      var end = a + MARK.length;
      if (p.length === end || p.charAt(end) === "/") {
        if (p.length === end) {
          return p + "/";
        }
        return p.substring(0, end + 1);
      }
    }
    if (p.endsWith("/")) {
      return p;
    }
    return p.replace(/\/[^/]+$/, "/");
  }

  function resolve(rel) {
    return new URL(String(rel), location.origin + portalBasePath()).toString();
  }

  global.MC1PORTAL = { portalBasePath: portalBasePath, resolve: resolve };
})(typeof window !== "undefined" ? window : this);
