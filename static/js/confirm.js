// ═══════════════════════════════════════════════════════
//  confirm.js — 确认对话框
// ═══════════════════════════════════════════════════════
window.App = window.App || {};

(function(App) {
  "use strict";

  var _confirmActive = false;

  App.showConfirm = function(title, message, onConfirm) {
    if (_confirmActive) return;
    _confirmActive = true;

    var HtmlUtils = App.HtmlUtils;
    var overlay = document.getElementById("confirmOverlay");
    var titleEl = document.getElementById("confirmTitle");
    var msgEl = document.getElementById("confirmMessage");
    var okBtn = document.getElementById("confirmOk");
    var cancelBtn = document.getElementById("confirmCancel");

    titleEl.textContent = title;
    HtmlUtils.setTrustedHtml(msgEl, message);

    overlay.classList.add("show");

    var _onOverlayClick, _onKeydown;

    function cleanup() {
      _confirmActive = false;
      overlay.classList.remove("show");
      okBtn.removeEventListener("click", handleOk);
      cancelBtn.removeEventListener("click", handleCancel);
      if (_onOverlayClick) overlay.removeEventListener("click", _onOverlayClick);
      if (_onKeydown) document.removeEventListener("keydown", _onKeydown);
    }

    function handleOk(e) {
      e.preventDefault();
      e.stopPropagation();
      cleanup();
      if (typeof onConfirm === "function") {
        try {
          var result = onConfirm();
          if (result && typeof result.catch === "function") {
            result.catch(function(err) { console.error("onConfirm error:", err); });
          }
        } catch (err) {
          console.error("onConfirm error:", err);
        }
      }
    }

    function handleCancel(e) {
      e.preventDefault();
      e.stopPropagation();
      cleanup();
    }

    okBtn.addEventListener("click", handleOk);
    cancelBtn.addEventListener("click", handleCancel);

    _onOverlayClick = function(e) {
      if (e.target === overlay) { cleanup(); }
    };
    overlay.addEventListener("click", _onOverlayClick);

    _onKeydown = function(e) {
      if (e.key === "Escape") { cleanup(); }
    };
    document.addEventListener("keydown", _onKeydown);
  };

})(window.App);
