/*  WeaveEstateHub – QR Camera Scanner Bridge
    Connects html5-qrcode library to Dash via hidden inputs and DOM manipulation.
*/

(function () {
  "use strict";

  let html5QrCode = null;
  let scanning = false;

  /* ---- helpers ---- */
  function resultBox(id) {
    return document.getElementById(id);
  }

  function setResult(boxId, status, title, name, detail) {
    const box = resultBox(boxId);
    if (!box) return;
    const color = status === "pass" ? "#28a745" : status === "fail" ? "#dc3545" : "#ffc107";
    box.innerHTML =
      '<div style="border:3px solid ' + color + ';border-radius:12px;padding:20px;text-align:center;margin-top:12px;background:' +
      (status === "pass" ? "#d4edda" : status === "fail" ? "#f8d7da" : "#fff3cd") + '">' +
        '<h2 style="color:' + color + ';margin:0 0 8px">' + title + '</h2>' +
        '<p style="font-weight:700;margin:0 0 4px;font-size:1.1rem">' + name + '</p>' +
        '<p style="margin:0;color:#555">' + detail + '</p>' +
      '</div>';
  }

  function clearResult(boxId) {
    const box = resultBox(boxId);
    if (box) box.innerHTML = "";
  }

  /* ---- evaluate via Flask API ---- */
  function evaluateQR(qrText, resultDivId) {
    fetch("/api/evaluate-qr", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ qr_data: qrText }),
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.status === "pass" || d.status === "fail") {
          setResult(resultDivId, d.status, d.title, d.name, d.detail);
          // Also add to recent-evaluations list
          addRecentEval(d.status, d.title, d.name, d.detail);
        } else {
          setResult(resultDivId, "warn", "ERROR", "QR Error", d.message || "Unknown error");
        }
      })
      .catch(function (err) {
        setResult(resultDivId, "warn", "NETWORK ERROR", "", err.toString());
      });
  }

  /* keep last 10 evaluations in-memory */
  var recentEvals = [];

  function addRecentEval(status, title, name, detail) {
    var ts = new Date().toLocaleTimeString();
    recentEvals.unshift({ ts: ts, status: status, title: title, name: name, detail: detail });
    if (recentEvals.length > 10) recentEvals.pop();
    renderRecentEvals();
  }

  function renderRecentEvals() {
    /* Try both possible containers */
    ["qr-recent-evals-admin", "qr-recent-evals-security"].forEach(function (id) {
      var el = document.getElementById(id);
      if (!el) return;
      if (recentEvals.length === 0) {
        el.innerHTML = '<p class="text-muted text-center mb-0">No recent evaluations.</p>';
        return;
      }
      var rows = recentEvals.map(function (e) {
        var badgeColor = e.status === "pass" ? "success" : "danger";
        return '<tr>' +
          '<td>' + e.ts + '</td>' +
          '<td><span class="badge bg-' + badgeColor + '">' + e.title + '</span></td>' +
          '<td>' + e.name + '</td>' +
          '<td class="small">' + e.detail + '</td>' +
          '</tr>';
      }).join("");
      el.innerHTML =
        '<table class="table table-sm table-hover mb-0">' +
          '<thead><tr><th>Time</th><th>Result</th><th>Name</th><th>Details</th></tr></thead>' +
          '<tbody>' + rows + '</tbody>' +
        '</table>';
    });
  }

  /* ---- start / stop camera ---- */
  function startScanner(readerId, resultDivId) {
    if (scanning) return;
    var readerEl = document.getElementById(readerId);
    if (!readerEl) return;
    readerEl.innerHTML = "";  // clear placeholder content

    html5QrCode = new Html5Qrcode(readerId);
    scanning = true;

    html5QrCode
      .start(
        { facingMode: "environment" },
        { fps: 10, qrbox: { width: 250, height: 250 } },
        function onScanSuccess(decodedText) {
          /* Pause scanning briefly to avoid duplicate reads */
          html5QrCode.pause(true);
          evaluateQR(decodedText, resultDivId);
          setTimeout(function () {
            if (scanning && html5QrCode) {
              try { html5QrCode.resume(); } catch (_) {}
            }
          }, 3000);
        },
        function onScanFailure() { /* ignore */ }
      )
      .catch(function (err) {
        readerEl.innerHTML =
          '<div class="text-center p-4">' +
            '<i class="fa fa-exclamation-triangle fa-3x text-warning mb-3"></i>' +
            '<p class="text-danger fw-bold">Camera access denied or unavailable</p>' +
            '<p class="text-muted small">' + err + '</p>' +
          '</div>';
        scanning = false;
      });
  }

  function stopScanner(readerId) {
    if (!scanning || !html5QrCode) return;
    html5QrCode
      .stop()
      .then(function () {
        scanning = false;
        html5QrCode = null;
        var el = document.getElementById(readerId);
        if (el) {
          el.innerHTML =
            '<div class="text-center p-4">' +
              '<i class="fa fa-qrcode fa-4x text-muted mb-3"></i>' +
              '<p class="text-muted">Camera stopped. Click <b>Start Camera</b> to scan again.</p>' +
            '</div>';
        }
      })
      .catch(function () {
        scanning = false;
      });
  }

  /* ---- wire up buttons via MutationObserver (Dash re-renders DOM) ---- */
  function wireButtons() {
    /* Admin evaluate-pass page */
    var adminStart = document.getElementById("admin-qr-start-btn");
    var adminStop  = document.getElementById("admin-qr-stop-btn");
    if (adminStart && !adminStart._wired) {
      adminStart._wired = true;
      adminStart.addEventListener("click", function () {
        startScanner("admin-qr-reader", "admin-qr-result");
      });
    }
    if (adminStop && !adminStop._wired) {
      adminStop._wired = true;
      adminStop.addEventListener("click", function () {
        stopScanner("admin-qr-reader");
      });
    }

    /* Security pass-evaluation page */
    var secStart = document.getElementById("sec-qr-start-btn");
    var secStop  = document.getElementById("sec-qr-stop-btn");
    if (secStart && !secStart._wired) {
      secStart._wired = true;
      secStart.addEventListener("click", function () {
        startScanner("sec-qr-reader", "sec-qr-result");
      });
    }
    if (secStop && !secStop._wired) {
      secStop._wired = true;
      secStop.addEventListener("click", function () {
        stopScanner("sec-qr-reader");
      });
    }
  }

  /* Observe DOM changes so we re-wire after Dash re-renders */
  var observer = new MutationObserver(function () { wireButtons(); });
  observer.observe(document.body, { childList: true, subtree: true });

  /* Also wire on initial load */
  document.addEventListener("DOMContentLoaded", wireButtons);
})();
