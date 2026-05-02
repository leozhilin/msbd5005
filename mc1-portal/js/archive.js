(function () {
  "use strict";

  var E = null;
  var man = null;
  var mammothMod = null;
  var currentTab = "person";
  var selName = null;
  var selOutlet = null;
  var outletSlugMap = null;
  var selArticle = null;

  function byId(id) { return document.getElementById(id); }

  function setActiveTab(t) {
    currentTab = t;
    ["person", "news"].forEach(function (x) {
      byId("tab-" + x).classList.toggle("active", x === t);
    });
    byId("list-person").style.display = t === "person" ? "block" : "none";
    byId("list-news").style.display = t === "news" ? "block" : "none";
  }

  function loadMammoth() {
    if (mammothMod) return Promise.resolve(mammothMod);
    if (window.mammoth) {
      mammothMod = window.mammoth;
      return Promise.resolve(mammothMod);
    }
    return new Promise(function (res, rej) {
      var s = document.createElement("script");
      s.src = "vendor/mammoth.browser.min.js";
      s.async = true;
      s.onload = function () {
        mammothMod = window.mammoth;
        res(mammothMod);
      };
      s.onerror = function () { rej(new Error("mammoth load")); };
      document.head.appendChild(s);
    });
  }

  function u(rel) {
    return window.MC1PORTAL && window.MC1PORTAL.resolve
      ? window.MC1PORTAL.resolve(rel)
      : rel;
  }

  function loadEmailIndex() {
    if (E) return Promise.resolve(E);
    return fetch(u("data/emails_by_person.json"))
      .then(function (r) { return r.json(); })
      .then(function (d) { E = d; return E; });
  }

  function renderMainPlaceholder(t) {
    byId("main-content").innerHTML = '<p class="arch-placeholder">' + t + "</p>";
  }

  function setHash() {
    if (currentTab === "person" && selName) {
      location.hash = "#/person/" + encodeURIComponent(selName);
    } else if (currentTab === "news" && selOutlet) {
      if (selArticle) {
        location.hash = "#/news/" + encodeURIComponent(selOutlet) + "/" + encodeURIComponent(selArticle);
      } else {
        location.hash = "#/news/" + encodeURIComponent(selOutlet);
      }
    }
  }

  function showPersonListActive() {
    var ul = byId("ul-persons");
    Array.prototype.forEach.call(ul.querySelectorAll("button"), function (b) {
      b.classList.toggle("sel", b.getAttribute("data-name") === selName);
    });
  }

  function openPerson(name) {
    if (!man || !man.resumes) return;
    selName = name;
    var item = (man.resumes || []).find(function (r) { return r.name === name; });
    if (!item) return;
    setActiveTab("person");
    showPersonListActive();
    var main = byId("main-content");
    main.innerHTML = '<p class="btn-loader arch-placeholder">Loading record…</p>';

    var pHead =
      '<div class="paper">' +
      '  <p class="paper-h">Personnel record</p>' +
      '  <h1 class="paper-title"></h1>' +
      '  <p class="paper-meta">Type: ' + (item.file.indexOf("Bio-") === 0 ? "Executive bio" : "Staff résumé") + " · Source file " + item.file + "</p>" +
      '  <p class="paper-actions"><a class="open-dl" href="" download>↓ Download .docx</a></p>' +
      '  <div class="doc-html" id="doc-body"></div>' +
      "</div>" +
      '<div class="paper" id="mail-paper"><p class="paper-h">Email traffic (deduplicated header index)</p><div id="mail-block"><p class="doc-empty">Loading email header index…</p></div></div>';

    main.innerHTML = pHead;
    main.querySelector("h1.paper-title").textContent = name;
    var dl = main.querySelector("a.open-dl");
    dl.setAttribute("href", item.path);
    dl.setAttribute("download", item.file);

    loadMammoth()
      .then(function () {
        return fetch(u(item.path));
      })
      .then(function (r) {
        if (!r.ok) throw new Error("docx " + r.status);
        return r.arrayBuffer();
      })
      .then(function (buf) {
        return mammothMod.convertToHtml({ arrayBuffer: buf });
      })
      .then(function (o) {
        byId("doc-body").innerHTML = o.value || "<p class=doc-empty>(No body text or conversion failed.)</p>";
      })
      .catch(function () {
        byId("doc-body").innerHTML =
          "<p class=doc-empty>Could not convert this Word file in the browser. Use Download .docx to open it locally.</p>";
      });

    loadEmailIndex().then(function () {
      var idxs = (E.indexByName && E.indexByName[name]) || [];
      var rows = E.rows || [];
      var block = byId("mail-block");
      if (idxs.length === 0) {
        block.innerHTML = "<p class=doc-empty>No email header rows matched this name.</p>";
        return;
      }
      var t =
        "<p class=paper-meta>" + idxs.length + " deduplicated header row(s). The same row may appear under multiple names when they share a thread.</p>" +
        '<div class=mail-table-wrap><table class=mail-table><thead><tr><th>From</th><th class=mail-td-to>To / Cc (summary)</th><th>Date</th><th class=col-subj>Subject</th></tr></thead><tbody>';
      idxs.forEach(function (i) {
        var e = rows[i];
        if (!e) return;
        var toFull = e.to || "";
        var toShow = toFull;
        if (toShow.length > 200) toShow = toShow.slice(0, 200) + "…";
        t +=
          "<tr><td>" +
          esc(e.from) +
          "</td><td class=mail-td-to title='" +
          esc(toFull) +
          "'>" +
          esc(toShow) +
          "</td><td>" +
          esc(e.date) +
          "</td><td class=col-subj>" +
          esc(e.subject) +
          "</td></tr>";
      });
      t += "</tbody></table></div>";
      block.innerHTML = t;
    });

    setHash();
  }

  function esc(s) {
    if (!s) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function openNewsArticle(outlet, file) {
    selOutlet = outlet;
    selArticle = file;
    setActiveTab("news");
    if (!outlet || !file) {
      renderMainPlaceholder("Choose an outlet on the left, then pick an article title.");
      return Promise.resolve();
    }
    var main = byId("main-content");
    main.innerHTML = '<p class="btn-loader arch-placeholder">Loading article…</p>';
    return ensureArticleList(outlet)
      .then(function (pack) {
        var art = (pack.articles || []).find(function (a) { return a.file === file; });
        if (!art) throw new Error("no art");
        return fetch(u(art.path));
      })
      .then(function (r) {
        if (!r || !r.ok) {
          throw new Error("HTTP " + (r && r.status));
        }
        return r.text();
      })
      .then(function (txt) {
        main.innerHTML =
          "<div class=paper><p class=paper-h>Press archive</p>" +
          "<h1 class=paper-title>" +
          esc(file) +
          "</h1><p class=news-meta>Outlet: " +
          esc(outlet) +
          "</p>" +
          '<div class=news-body></div></div>';
        main.querySelector(".news-body").textContent = txt;
        setNewsSel();
        setHash();
      })
      .catch(function (err) {
        main.innerHTML =
          '<p class="arch-placeholder">Could not load this article (' +
          esc(String(err && err.message ? err.message : err)) +
          "). Check that <code>MC1/News Articles</code> is available to the server.</p>";
      });
  }

  function setNewsSel() {
    if (!outletSlugMap) return;
    byId("ul-outlets")
      .querySelectorAll("button")
      .forEach(function (b) {
        b.classList.toggle("sel", b.getAttribute("data-outlet") === selOutlet);
      });
    if (byId("ul-art")) {
      byId("ul-art").querySelectorAll("button").forEach(function (b) {
        b.classList.toggle("sel", b.getAttribute("data-file") === selArticle);
      });
    }
  }

  function ensureArticleList(outlet) {
    var ulA = byId("ul-art");
    return fetch(u("data/outlet_news/_index.json"))
      .then(function (r) { return r.json(); })
      .then(function (idx) {
        var slug = idx[outlet];
        if (!slug) throw new Error("no outlet");
        return fetch(u("data/outlet_news/" + slug + ".json"));
      })
      .then(function (r) { return r.json(); })
      .then(function (pack) {
        ulA.innerHTML = "";
        (pack.articles || []).forEach(function (a) {
          var li = document.createElement("li");
          var btn = document.createElement("button");
          btn.setAttribute("data-file", a.file);
          btn.textContent = a.file;
          btn.type = "button";
          btn.addEventListener("click", function () {
            openNewsArticle(outlet, a.file);
          });
          li.appendChild(btn);
          ulA.appendChild(li);
        });
        if (byId("arch-art-h")) byId("arch-art-h").style.display = "block";
        return pack;
      });
  }

  function loadOutletArticles(outlet) {
    selOutlet = outlet;
    selArticle = null;
    setActiveTab("news");
    setNewsSel();
    var ulA = byId("ul-art");
    ulA.innerHTML = "<li>…</li>";
    return ensureArticleList(outlet)
      .then(function () {
        setNewsSel();
        renderMainPlaceholder("Select an article under the outlet on the left.");
        setHash();
      });
  }

  function applyHash() {
    var h = (location.hash || "").replace(/^#/, "").replace(/^\//, "");
    if (h.indexOf("person/") === 0) {
      var nm = decodeURIComponent(h.slice(7));
      if (nm) {
        setActiveTab("person");
        openPerson(nm);
        return;
      }
    }
    if (h.indexOf("news/") === 0) {
      var rest = h.slice(5);
      var parts = rest.split("/");
      if (parts.length >= 1 && parts[0]) {
        setActiveTab("news");
        var o = decodeURIComponent(parts[0]);
        selOutlet = o;
        if (parts.length >= 2 && parts[1]) {
          var f = decodeURIComponent(parts[1].replace(/\/+$/, ""));
          openNewsArticle(o, f);
        } else {
          loadOutletArticles(o);
        }
        return;
      }
    }
  }

  function init() {
    fetch(u("data/manifest.json"))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        man = d;
        var ulp = byId("ul-persons");
        ulp.innerHTML = "";
        (d.resumes || []).forEach(function (r) {
          var li = document.createElement("li");
          var b = document.createElement("button");
          b.setAttribute("data-name", r.name);
          b.type = "button";
          b.textContent = r.name;
          b.addEventListener("click", function () { openPerson(r.name); });
          li.appendChild(b);
          ulp.appendChild(li);
        });
        return fetch(u("data/outlet_news/_index.json"));
      })
      .then(function (r) { return r.json(); })
      .then(function (idx) {
        outletSlugMap = idx;
        var ulo = byId("ul-outlets");
        ulo.innerHTML = "";
        (man.outlets || []).forEach(function (o) {
          var li = document.createElement("li");
          var b = document.createElement("button");
          b.setAttribute("data-outlet", o.outlet);
          b.type = "button";
          b.textContent = o.outlet + " (" + o.count + ")";
          b.addEventListener("click", function () { loadOutletArticles(o.outlet); });
          li.appendChild(b);
          ulo.appendChild(li);
        });
        applyHash();
        if (!location.hash) {
          renderMainPlaceholder("Select a person for résumé and email headers, or an outlet and article for full text.");
        }
      })
      .catch(function () {
        byId("main-content").innerHTML =
          '<p class="arch-placeholder" style="color:#e99">Could not load <code>data/manifest.json</code>. Serve this folder over HTTP and ensure the data bundle is present.</p>';
      });

    byId("tab-person").addEventListener("click", function () {
      setActiveTab("person");
      if (selName) openPerson(selName);
      else renderMainPlaceholder("Select a person on the left.");
    });
    byId("tab-news").addEventListener("click", function () {
      setActiveTab("news");
      if (selOutlet) loadOutletArticles(selOutlet);
      else {
        byId("ul-art").innerHTML = "";
        byId("arch-art-h").style.display = "none";
        renderMainPlaceholder("Choose an outlet first.");
      }
    });
    window.addEventListener("hashchange", applyHash);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
